"""Transaction analysis service."""

from datetime import date
from typing import Dict, List, Optional

from models.transaction import Transaction
from repositories.transactions import TransactionRepository


class AnalysisService:
    """Aggregation and summary of transaction data."""

    def __init__(self, db_manager):
        self.transactions = TransactionRepository(db_manager)

    def get_period_transactions(
        self,
        start_month: date,
        end_month: date,
        category_ids: Optional[List[int]] = None,
    ) -> Dict[str, Dict[str, List[Transaction]]]:
        """Get transactions for a period, organized by basis and month.

        Returns transactions grouped by basis type (cash/accrual) with monthly breakdowns.

        Args:
            start_month: Start of period (date object, day component ignored).
            end_month: End of period (date object, day component ignored).
            category_ids: Optional list of category IDs to filter by.

        Returns:
            Dictionary with basis type keys ("cash_basis", "accrual_basis") containing
            month keys (format: "YYYY/MM") mapped to transaction lists:
            - "cash_basis": Dictionary of months with non-amortized transactions
            - "accrual_basis": Dictionary of months with accrued transactions
        """
        result = {
            "cash_basis": {},
            "accrual_basis": {},
        }

        current_year = start_month.year
        current_month = start_month.month
        end_year = end_month.year
        end_month_num = end_month.month

        while (current_year, current_month) <= (end_year, end_month_num):
            month_key = f"{current_year:04d}/{current_month:02d}"

            cash_basis = self.transactions.get_transactions_by_month(
                current_year,
                current_month,
                exclude_amortized=True,
                category_ids=category_ids,
            )

            accrual_basis = self.transactions.get_accrued_transactions_by_month(
                current_year,
                current_month,
                category_ids=category_ids,
            )

            result["cash_basis"][month_key] = cash_basis
            result["accrual_basis"][month_key] = accrual_basis

            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1

        return result

    def get_period_summary(
        self,
        start_month: date,
        end_month: date,
        category_ids: Optional[List[int]] = None,
    ) -> Dict[str, Dict[str, Dict]]:
        """Get summarized transaction data for a period, organized by basis and month.

        Returns aggregated income, expenses, and category breakdowns for each month.

        Args:
            start_month: Start of period (date object, day component ignored).
            end_month: End of period (date object, day component ignored).
            category_ids: Optional list of category IDs to filter by.

        Returns:
            Dictionary with basis type keys ("cash_basis", "accrual_basis") containing
            month keys (format: "YYYY/MM") mapped to summary dictionaries:
            - "income_total": Total income for the month (Decimal)
            - "expense_total": Total expenses for the month (Decimal)
            - "net": Net amount (income - expenses) in cents (int)
            - "expenses_by_category": Dict mapping category_id to expense amount in cents
        """
        transactions_data = self.get_period_transactions(
            start_month, end_month, category_ids
        )

        result = {
            "cash_basis": {},
            "accrual_basis": {},
        }

        for basis_type in ["cash_basis", "accrual_basis"]:
            for month_key, transactions in transactions_data[basis_type].items():
                income_total = 0
                expense_total = 0
                expenses_by_category: Dict[int, int] = {}

                for transaction in transactions:
                    if transaction.transaction_type == "income":
                        income_total += transaction.amount
                    elif transaction.transaction_type == "expense":
                        expense_total += transaction.amount

                        category_id = (
                            transaction.category_id
                            if transaction.category_id is not None
                            else 0
                        )

                        if category_id not in expenses_by_category:
                            expenses_by_category[category_id] = 0
                        expenses_by_category[category_id] += transaction.amount

                net = income_total - expense_total

                result[basis_type][month_key] = {
                    "income_total": income_total,
                    "expense_total": expense_total,
                    "net": net,
                    "expenses_by_category": expenses_by_category,
                }

        return result
