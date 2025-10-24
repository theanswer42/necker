#!/usr/bin/env python3

import sys
import argparse
from pathlib import Path
from services import accounts as account_service
from services import transactions as transaction_service
from ingestion import get_ingestion_module


def ingest_transactions(account_name: str, csv_file: str):
    """Ingest transactions from a CSV file for a specific account.

    Args:
        account_name: Name of the account to ingest transactions for.
        csv_file: Path to the CSV file to ingest.
    """
    # Validate CSV file exists
    csv_path = Path(csv_file)
    if not csv_path.exists():
        print(f"Error: File not found: {csv_file}")
        sys.exit(1)

    # Look up account by name
    account = account_service.find_by_name(account_name)
    if not account:
        print(f"Error: Account '{account_name}' not found.")
        print(
            "\nUse 'python -m cli.accounts --list-accounts' to see available accounts."
        )
        sys.exit(1)

    print(f"Ingesting transactions for account: {account.name} (ID: {account.id})")
    print(f"Account type: {account.type}")
    print(f"CSV file: {csv_file}")
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


def main():
    parser = argparse.ArgumentParser(
        description="Transaction ingestion CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m cli.transactions --account-name bofa_checking transactions.csv
  python -m cli.transactions --account-name amex samples/amex.csv
        """,
    )
    parser.add_argument(
        "--account-name",
        required=True,
        help="Name of the account to import transactions for",
    )
    parser.add_argument(
        "csv_file",
        help="Path to the CSV file to ingest",
    )

    args = parser.parse_args()

    try:
        ingest_transactions(args.account_name, args.csv_file)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
