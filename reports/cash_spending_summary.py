"""Cash-basis spending summary report."""

from typing import List, Optional

from models.reports import MonthSpendingSummary
from reports._aggregation import summarize_transactions
from reports.month_transactions import MonthTransactionsReport


class CashSpendingSummaryReport:
    """Income, expenses, net, and per-category breakdown on cash basis."""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    def run(
        self,
        year: int,
        month: int,
        category_ids: Optional[List[int]] = None,
    ) -> MonthSpendingSummary:
        month_txns = MonthTransactionsReport(self.db_manager).run(
            year, month, basis="cash", category_ids=category_ids
        )
        return summarize_transactions(year, month, "cash", month_txns.transactions)
