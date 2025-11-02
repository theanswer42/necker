"""Transaction analysis tools."""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from models.transaction import Transaction


def get_period_transactions(
    services,
    start_month: date,
    end_month: date,
    category_ids: Optional[List[int]] = None,
) -> Dict[str, Dict[str, List[Transaction]]]:
    """Get transactions for a period, organized by basis and month.

    Returns transactions grouped by basis type (cash/accrual) with monthly breakdowns.

    Args:
        services: Services container with transaction service.
        start_month: Start of period (date object, day component ignored).
        end_month: End of period (date object, day component ignored).
        category_ids: Optional list of category IDs to filter by.

    Returns:
        Dictionary with basis type keys ("cash_basis", "accrual_basis") containing
        month keys (format: "YYYY/MM") mapped to transaction lists:
        - "cash_basis": Dictionary of months with non-amortized transactions
        - "accrual_basis": Dictionary of months with accrued transactions

    Example:
        {
            "cash_basis": {
                "2024/01": [Transaction(...), ...],
                "2024/02": [Transaction(...), ...],
            },
            "accrual_basis": {
                "2024/01": [Transaction(...), ...],
                "2024/02": [Transaction(...), ...],
            },
        }
    """
    result = {
        "cash_basis": {},
        "accrual_basis": {},
    }

    # Extract year and month, ignoring day
    current_year = start_month.year
    current_month = start_month.month
    end_year = end_month.year
    end_month_num = end_month.month

    # Iterate through each month in the range (inclusive)
    while (current_year, current_month) <= (end_year, end_month_num):
        # Format month key as "YYYY/MM"
        month_key = f"{current_year:04d}/{current_month:02d}"

        # Fetch cash basis transactions (exclude amortized)
        cash_basis = services.transactions.get_transactions_by_month(
            current_year,
            current_month,
            exclude_amortized=True,
            category_ids=category_ids,
        )

        # Fetch accrual basis transactions
        accrual_basis = services.transactions.get_accrued_transactions_by_month(
            current_year,
            current_month,
            category_ids=category_ids,
        )

        result["cash_basis"][month_key] = cash_basis
        result["accrual_basis"][month_key] = accrual_basis

        # Move to next month
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    return result


def get_period_summary(
    services,
    start_month: date,
    end_month: date,
    category_ids: Optional[List[int]] = None,
) -> Dict[str, Dict[str, Dict]]:
    """Get summarized transaction data for a period, organized by basis and month.

    Returns aggregated income, expenses, and category breakdowns for each month.

    Args:
        services: Services container with transaction service.
        start_month: Start of period (date object, day component ignored).
        end_month: End of period (date object, day component ignored).
        category_ids: Optional list of category IDs to filter by.

    Returns:
        Dictionary with basis type keys ("cash_basis", "accrual_basis") containing
        month keys (format: "YYYY/MM") mapped to summary dictionaries:
        - "income_total": Total income for the month (Decimal)
        - "expense_total": Total expenses for the month (Decimal)
        - "net": Net amount (income - expenses) (Decimal)
        - "expenses_by_category": Dict mapping category_id to expense amount (Decimal)
          (category_id=0 for uncategorized transactions)

    Example:
        {
            "cash_basis": {
                "2024/01": {
                    "income_total": Decimal("1000.00"),
                    "expense_total": Decimal("500.00"),
                    "net": Decimal("500.00"),
                    "expenses_by_category": {
                        1: Decimal("200.00"),  # Food category
                        2: Decimal("300.00"),  # Transportation category
                    }
                },
                "2024/02": {...},
            },
            "accrual_basis": {
                "2024/01": {...},
                "2024/02": {...},
            },
        }
    """
    # Get all transactions for the period
    transactions_data = get_period_transactions(
        services, start_month, end_month, category_ids
    )

    result = {
        "cash_basis": {},
        "accrual_basis": {},
    }

    # Process each basis type
    for basis_type in ["cash_basis", "accrual_basis"]:
        # Process each month
        for month_key, transactions in transactions_data[basis_type].items():
            income_total = Decimal("0")
            expense_total = Decimal("0")
            expenses_by_category: Dict[int, Decimal] = {}

            # Aggregate transactions
            for transaction in transactions:
                if transaction.type == "income":
                    income_total += transaction.amount
                elif transaction.type == "expense":
                    expense_total += transaction.amount

                    # Use category_id=0 for uncategorized transactions
                    category_id = (
                        transaction.category_id
                        if transaction.category_id is not None
                        else 0
                    )

                    if category_id not in expenses_by_category:
                        expenses_by_category[category_id] = Decimal("0")
                    expenses_by_category[category_id] += transaction.amount

            # Calculate net
            net = income_total - expense_total

            # Store summary for this month
            result[basis_type][month_key] = {
                "income_total": income_total,
                "expense_total": expense_total,
                "net": net,
                "expenses_by_category": expenses_by_category,
            }

    return result
