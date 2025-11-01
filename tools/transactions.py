"""Transaction analysis tools."""

from datetime import date
from typing import Dict, List, Optional
from models.transaction import Transaction


def get_period_transactions(
    services,
    start_month: date,
    end_month: date,
    category_ids: Optional[List[int]] = None,
) -> Dict[str, Dict[str, List[Transaction]]]:
    """Get transactions for a period, organized by month and basis.

    Returns transactions grouped by month with both cash and accrual basis views.

    Args:
        services: Services container with transaction service.
        start_month: Start of period (date object, day component ignored).
        end_month: End of period (date object, day component ignored).
        category_ids: Optional list of category IDs to filter by.

    Returns:
        Dictionary with month keys (format: "YYYY/MM") and values containing:
        - "cash_basis": List of non-amortized transactions for that month
        - "accrual_basis": List of accrued transactions for that month

    Example:
        {
            "2024/01": {
                "cash_basis": [Transaction(...), ...],
                "accrual_basis": [Transaction(...), ...],
            },
            "2024/02": {
                "cash_basis": [...],
                "accrual_basis": [...],
            },
        }
    """
    result = {}

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

        result[month_key] = {
            "cash_basis": cash_basis,
            "accrual_basis": accrual_basis,
        }

        # Move to next month
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    return result
