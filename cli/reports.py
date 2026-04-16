#!/usr/bin/env python3
"""CLI commands for analytical reports."""

import sys

from logger import get_logger
from repositories.categories import CategoryRepository
from reports.accrual_spending_summary import AccrualSpendingSummaryReport
from reports.cash_spending_summary import CashSpendingSummaryReport
from reports.month_transactions import MonthTransactionsReport

logger = get_logger()

VALID_BASES = ("cash", "accrual")


def _format_amount(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _parse_month_arg(value: str) -> tuple[int, int]:
    """Parse a YYYY/MM string into (year, month). Raises ValueError on failure."""
    year_str, month_str = value.split("/")
    year = int(year_str)
    month = int(month_str)
    if not (1 <= month <= 12):
        raise ValueError(f"month {month} out of range")
    return year, month


def _parse_month_or_exit(value: str) -> tuple[int, int]:
    try:
        return _parse_month_arg(value)
    except (ValueError, AttributeError):
        logger.error(f"Invalid --month value '{value}'. Expected YYYY/MM.")
        sys.exit(1)


def cmd_transactions(args, db_manager, config):
    year, month = _parse_month_or_exit(args.month)
    if args.basis not in VALID_BASES:
        logger.error(f"--basis must be one of {', '.join(VALID_BASES)}")
        sys.exit(1)

    report = MonthTransactionsReport(db_manager).run(year, month, args.basis)

    category_names = {c.id: c.name for c in CategoryRepository(db_manager).find_all()}

    print(f"\nTransactions: {year:04d}/{month:02d} ({report.basis} basis)")
    print("=" * 80)

    if not report.transactions:
        print("(no transactions)")
        return

    print(f"{'Date':<12} {'Description':<40} {'Amount':>12}  Category")
    print("-" * 80)
    for t in report.transactions:
        category = (
            category_names.get(t.category_id, "") if t.category_id is not None else ""
        )
        desc = (t.description or "")[:40]
        print(
            f"{t.transaction_date.isoformat():<12} {desc:<40} "
            f"{_format_amount(t.amount):>12}  {category}"
        )


def cmd_spending_summary(args, db_manager, config):
    year, month = _parse_month_or_exit(args.month)
    if args.basis not in VALID_BASES:
        logger.error(f"--basis must be one of {', '.join(VALID_BASES)}")
        sys.exit(1)

    if args.basis == "cash":
        summary = CashSpendingSummaryReport(db_manager).run(year, month)
    else:
        summary = AccrualSpendingSummaryReport(db_manager).run(year, month)

    category_names = {c.id: c.name for c in CategoryRepository(db_manager).find_all()}

    print(f"\nSpending Summary: {year:04d}/{month:02d} ({summary.basis} basis)")
    print("=" * 80)
    print(f"Income:   {_format_amount(summary.income_total):>14}")
    print(f"Expenses: {_format_amount(summary.expense_total):>14}")
    print(f"Net:      {_format_amount(summary.net):>14}")

    if summary.expenses_by_category:
        print("\nExpenses by Category:")
        for cat_id, amount in sorted(
            summary.expenses_by_category.items(), key=lambda item: -item[1]
        ):
            label = (
                category_names.get(cat_id, "(uncategorized)")
                if cat_id
                else "(uncategorized)"
            )
            print(f"  {label:<30} {_format_amount(amount):>12}")


def setup_parser(subparsers):
    """Setup reports subcommand parser."""
    parser = subparsers.add_parser(
        "reports",
        help="Run analytical reports",
        description="Run reports that aggregate transactions.",
    )

    reports_subparsers = parser.add_subparsers(
        title="subcommands",
        description="Available reports",
        dest="subcommand",
        required=True,
    )

    txn_parser = reports_subparsers.add_parser(
        "transactions",
        help="List transactions for a month on the given basis",
    )
    txn_parser.add_argument("--month", required=True, help="Month in YYYY/MM format")
    txn_parser.add_argument(
        "--basis",
        required=True,
        choices=VALID_BASES,
        help="Reporting basis: 'cash' or 'accrual'",
    )
    txn_parser.set_defaults(func=cmd_transactions)

    summary_parser = reports_subparsers.add_parser(
        "spending-summary",
        help="Show income, expenses, net, and category breakdown for a month",
    )
    summary_parser.add_argument(
        "--month", required=True, help="Month in YYYY/MM format"
    )
    summary_parser.add_argument(
        "--basis",
        required=True,
        choices=VALID_BASES,
        help="Reporting basis: 'cash' or 'accrual'",
    )
    summary_parser.set_defaults(func=cmd_spending_summary)
