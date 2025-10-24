#!/usr/bin/env python3

import sys
from pathlib import Path
from services import accounts as account_service
from services import transactions as transaction_service
from ingestion import get_ingestion_module


def cmd_ingest(args):
    """Ingest transactions from a CSV file for a specific account.

    Args:
        args: Parsed command-line arguments with csv_file and account_name
    """
    # Validate CSV file exists
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"Error: File not found: {args.csv_file}")
        sys.exit(1)

    # Look up account by name
    account = account_service.find_by_name(args.account_name)
    if not account:
        print(f"Error: Account '{args.account_name}' not found.")
        print("\nUse 'python -m cli accounts list' to see available accounts.")
        sys.exit(1)

    print(f"Ingesting transactions for account: {account.name} (ID: {account.id})")
    print(f"Account type: {account.type}")
    print(f"CSV file: {args.csv_file}")
    print("-" * 80)

    # Get the ingestion module for this account type
    try:
        ingestion_module = get_ingestion_module(account.type)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Ingest transactions from CSV
    try:
        with open(csv_path, "r") as f:
            transactions = ingestion_module.ingest(f, account.id)

        print(f"\nParsed {len(transactions)} transactions from CSV")

        if not transactions:
            print("No transactions to import.")
            return

        # Bulk insert transactions
        inserted_count = transaction_service.bulk_create(transactions)

        print(f"✓ Successfully inserted {inserted_count} transactions")

        if inserted_count < len(transactions):
            skipped = len(transactions) - inserted_count
            print(f"  ({skipped} duplicate transaction(s) skipped)")

    except Exception as e:
        print(f"\nError during ingestion: {e}")
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
