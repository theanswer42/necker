"""Month transactions report."""

from typing import List, Optional

from models.reports import MonthTransactions
from repositories.transactions import TransactionRepository


class MonthTransactionsReport:
    """Return the transactions for a single month on cash or accrual basis."""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    def run(
        self,
        year: int,
        month: int,
        basis: str,
        category_ids: Optional[List[int]] = None,
    ) -> MonthTransactions:
        repo = TransactionRepository(self.db_manager)

        if basis == "cash":
            transactions = repo.get_transactions_by_month(
                year,
                month,
                exclude_amortized=True,
                category_ids=category_ids,
            )
        elif basis == "accrual":
            transactions = repo.get_accrued_transactions_by_month(
                year,
                month,
                category_ids=category_ids,
            )
        else:
            raise ValueError(f"basis must be 'cash' or 'accrual', got {basis!r}")

        return MonthTransactions(
            year=year, month=month, basis=basis, transactions=transactions
        )
