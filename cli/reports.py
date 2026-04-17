#!/usr/bin/env python3
"""CLI commands for analytical reports."""

import sys

from logger import get_logger
from reports.accrual_spending_summary import AccrualSpendingSummaryReport
from reports.cash_spending_summary import CashSpendingSummaryReport
from reports.month_transactions import MonthTransactionsReport

logger = get_logger()

VALID_BASES = ("cash", "accrual")


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


def cmd_transactions(args, db_manager, config, output):
    year, month = _parse_month_or_exit(args.month)
    if args.basis not in VALID_BASES:
        logger.error(f"--basis must be one of {', '.join(VALID_BASES)}")
        sys.exit(1)

    report = MonthTransactionsReport(db_manager).run(year, month, args.basis)

    output.section(
        f"Transactions: {year:04d}/{month:02d} ({report.basis} basis)", report
    )


def cmd_spending_summary(args, db_manager, config, output):
    year, month = _parse_month_or_exit(args.month)
    if args.basis not in VALID_BASES:
        logger.error(f"--basis must be one of {', '.join(VALID_BASES)}")
        sys.exit(1)

    if args.basis == "cash":
        summary = CashSpendingSummaryReport(db_manager).run(year, month)
    else:
        summary = AccrualSpendingSummaryReport(db_manager).run(year, month)

    output.section(
        f"Spending Summary: {year:04d}/{month:02d} ({summary.basis} basis)", summary
    )


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
