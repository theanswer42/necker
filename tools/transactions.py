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
