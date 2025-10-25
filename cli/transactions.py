#!/usr/bin/env python3

import sys
from pathlib import Path
from ingestion import get_ingestion_module
from logger import get_logger

logger = get_logger()


def cmd_ingest(args, services):
    """Ingest transactions from a CSV file for a specific account.

    Args:
        args: Parsed command-line arguments with csv_file and account_name
        services: Services container with accounts and transactions services
    """
    # Validate CSV file exists
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        logger.error(f"File not found: {args.csv_file}")
        sys.exit(1)

    # Look up account by name
    account = services.accounts.find_by_name(args.account_name)
    if not account:
        logger.error(f"Account '{args.account_name}' not found.")
        logger.info("Use 'python -m cli accounts list' to see available accounts.")
        sys.exit(1)

    logger.info(
        f"Ingesting transactions for account: {account.name} (ID: {account.id})"
    )
    logger.info(f"Account type: {account.type}")
    logger.info(f"CSV file: {args.csv_file}")
    logger.info("-" * 80)

    # Get the ingestion module for this account type
    try:
        ingestion_module = get_ingestion_module(account.type)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    # Ingest transactions from CSV
    try:
        with open(csv_path, "r") as f:
            transactions = ingestion_module.ingest(f, account.id)

        logger.info(f"\nParsed {len(transactions)} transactions from CSV")

        if not transactions:
            logger.info("No transactions to import.")
            return

        # Bulk insert transactions
        inserted_count = services.transactions.bulk_create(transactions)

        logger.info(f"✓ Successfully inserted {inserted_count} transactions")

        if inserted_count < len(transactions):
            skipped = len(transactions) - inserted_count
            logger.info(f"  ({skipped} duplicate transaction(s) skipped)")

    except Exception as e:
        logger.error(f"Error during ingestion: {e}")
        sys.exit(1)


def setup_parser(subparsers):
    """Setup transactions subcommand parser.

    Args:
        subparsers: The subparsers object from the main CLI
    """
    parser = subparsers.add_parser(
        "transactions",
        help="Import and manage transactions",
        description="Import transactions from CSV files",
    )

    # Add subcommands for transactions
    transactions_subparsers = parser.add_subparsers(
        title="subcommands",
        description="Available transaction commands",
        dest="subcommand",
        required=True,
    )

    # transactions ingest
    ingest_parser = transactions_subparsers.add_parser(
        "ingest",
        help="Ingest transactions from a CSV file",
        epilog="""
Examples:
  python -m cli transactions ingest transactions.csv --account-name bofa_checking
  python -m cli transactions ingest samples/amex.csv --account-name amex_card
        """,
    )
    ingest_parser.add_argument(
        "csv_file",
        help="Path to the CSV file to ingest",
    )
    ingest_parser.add_argument(
        "--account-name",
        required=True,
        help="Name of the account to import transactions for",
    )
    ingest_parser.set_defaults(func=cmd_ingest)
