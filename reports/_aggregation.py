"""Shared aggregation helpers for spending summary reports."""

from typing import Iterable

from models.reports import MonthSpendingSummary
from models.transaction import Transaction


def summarize_transactions(
    year: int, month: int, basis: str, transactions: Iterable[Transaction]
) -> MonthSpendingSummary:
    """Aggregate a list of transactions into a MonthSpendingSummary.

    Uses category_id=0 for uncategorized expenses.
    """
    income_total = 0
    expense_total = 0
    expenses_by_category: dict[int, int] = {}

    for transaction in transactions:
        if transaction.transaction_type == "income":
            income_total += transaction.amount
        elif transaction.transaction_type == "expense":
            expense_total += transaction.amount
            category_id = (
                transaction.category_id if transaction.category_id is not None else 0
            )
            expenses_by_category[category_id] = (
                expenses_by_category.get(category_id, 0) + transaction.amount
            )

    return MonthSpendingSummary(
        year=year,
        month=month,
        basis=basis,
        income_total=income_total,
        expense_total=expense_total,
        net=income_total - expense_total,
        expenses_by_category=expenses_by_category,
    )
