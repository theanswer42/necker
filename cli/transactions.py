#!/usr/bin/env python3

import sys
import csv
from pathlib import Path
from logger import get_logger
from repositories.accounts import AccountRepository
from repositories.categories import CategoryRepository
from repositories.transactions import TransactionRepository
from services.ingestion import IngestionService

logger = get_logger()


def cmd_ingest(args, db_manager, config):
    """Ingest transactions from a CSV file for a specific account.

    Args:
        args: Parsed command-line arguments with csv_file and account_name
        db_manager: Database manager instance
        config: Application configuration
    """
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        logger.error(f"File not found: {args.csv_file}")
        sys.exit(1)

    account = AccountRepository(db_manager).find_by_name(args.account_name)
    if not account:
        logger.error(f"Account '{args.account_name}' not found.")
        logger.info("Use 'python -m cli accounts list' to see available accounts.")
        sys.exit(1)

    logger.info(
        f"Ingesting transactions for account: {account.name} (ID: {account.id})"
    )
    logger.info(f"Account type: {account.account_type}")
    logger.info(f"CSV file: {args.csv_file}")
    logger.info("-" * 80)

    try:
        result = IngestionService(db_manager, config).ingest_csv(csv_path, account)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during ingestion: {e}")
        sys.exit(1)

    logger.info(f"\nParsed {result['parsed']} transactions from CSV")

    if result["parsed"] == 0:
        logger.info("No transactions to import.")
        return

    if result["archive_filename"]:
        archive_path = config.archive_dir / result["archive_filename"]
        logger.info(f"Archived CSV to: {archive_path}")

    logger.info(f"Created data import record (ID: {result['data_import_id']})")
    logger.info(f"✓ Successfully inserted {result['inserted']} transactions")

    if result["skipped"] > 0:
        logger.info(f"  ({result['skipped']} duplicate transaction(s) skipped)")

    if result["inserted"] > 0:
        if result["categorized"] > 0:
            logger.info(f"✓ Auto-categorized {result['categorized']} transaction(s)")
        else:
            logger.info("No transactions were auto-categorized")


def cmd_set_category(args, db_manager, config):
    """Set the category for a transaction.

    Args:
        args: Parsed command-line arguments with transaction_id and category
        db_manager: Database manager instance
        config: Application configuration
    """
    transactions_repo = TransactionRepository(db_manager)
    categories_repo = CategoryRepository(db_manager)

    transaction_id = args.transaction_id
    category_input = args.category

    # Look up transaction
    transaction = transactions_repo.find(transaction_id)
    if not transaction:
        logger.error(f"Transaction with ID '{transaction_id}' not found.")
        sys.exit(1)

    # Look up category (try as ID first, then by name)
    category = None
    try:
        category_id = int(category_input)
        category = categories_repo.find(category_id)
    except ValueError:
        # Not a number, try as category name
        category = categories_repo.find_by_name(category_input)

    if not category:
        logger.error(f"Category '{category_input}' not found.")
        logger.info("Use 'python -m cli categories list' to see available categories.")
        sys.exit(1)

    # Update transaction category_id
    try:
        transaction.category_id = category.id
        success = transactions_repo.update(transaction, ["category_id"])

        if not success:
            logger.error("Failed to update transaction.")
            sys.exit(1)

        logger.info("✓ Transaction categorized successfully")
        logger.info(f"  Transaction: {transaction.description[:50]}...")
        logger.info(f"  Category: {category.name}")

    except Exception as e:
        logger.error(f"Error updating transaction: {e}")
        sys.exit(1)


def cmd_export(args, db_manager, config):
    """Export transactions to CSV.

    Args:
        args: Parsed command-line arguments
        db_manager: Database manager instance
        config: Application configuration
    """
    accounts_repo = AccountRepository(db_manager)
    transactions_repo = TransactionRepository(db_manager)
    categories_repo = CategoryRepository(db_manager)

    # Validate that both --start-date and --end-date are provided together
    if args.start_date and not args.end_date:
        logger.error("--start-date requires --end-date to be specified")
        sys.exit(1)
    if args.end_date and not args.start_date:
        logger.error("--end-date requires --start-date to be specified")
        sys.exit(1)

    # Determine date range based on --month or --start-date/--end-date
    account_id = None

    # Handle account filter if specified
    if args.account:
        account = accounts_repo.find_by_name(args.account)
        if not account:
            logger.error(f"Account '{args.account}' not found.")
            logger.info("Use 'python -m cli accounts list' to see available accounts.")
            sys.exit(1)
        account_id = account.id
        logger.info(f"Filtering by account: {account.name}")

    # Fetch transactions based on date parameters
    try:
        if args.month:
            # Parse month in format YYYY/MM
            year, month = args.month.split("/")
            year = int(year)
            month = int(month)

            if month < 1 or month > 12:
                logger.error("Month must be between 1 and 12")
                sys.exit(1)

            logger.info(f"Exporting transactions for {year}/{month:02d}")
            transactions = transactions_repo.get_transactions_by_month(
                year, month, account_id=account_id
            )
        else:
            # Parse start and end dates in format YYYY/MM/DD
            start_year, start_month, start_day = args.start_date.split("/")
            start_date = (
                f"{int(start_year):04d}-{int(start_month):02d}-{int(start_day):02d}"
            )

            end_year, end_month, end_day = args.end_date.split("/")
            end_date = f"{int(end_year):04d}-{int(end_month):02d}-{int(end_day):02d}"

            logger.info(f"Exporting transactions from {start_date} to {end_date}")
            transactions = transactions_repo.get_transactions_by_date_range(
                start_date, end_date, account_id=account_id
            )

    except (ValueError, IndexError) as e:
        logger.error(f"Invalid date format: {e}")
        logger.error(
            "Use YYYY/MM format for --month or YYYY/MM/DD format for --start-date and --end-date"
        )
        sys.exit(1)

    if not transactions:
        logger.info("No transactions found for the specified criteria.")
        sys.exit(0)

    logger.info(f"Found {len(transactions)} transaction(s)")

    # Get all accounts and categories for name lookups
    accounts = accounts_repo.find_all()
    categories = categories_repo.find_all()

    # Build lookup dictionaries
    account_map = {acc.id: acc.name for acc in accounts}
    category_map = {cat.id: cat.name for cat in categories}

    # Write to CSV
    try:
        output_path = Path(args.output)

        # Create parent directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(
                [
                    "id",
                    "transaction_date",
                    "post_date",
                    "description",
                    "account_name",
                    "bank_category",
                    "category_name",
                    "auto_category_name",
                    "merchant_name",
                    "auto_merchant_name",
                    "amount",
                    "transaction_type",
                    "data_import_id",
                    "amortize_months",
                    "amortize_end_date",
                ]
            )

            # Write data rows
            for t in transactions:
                writer.writerow(
                    [
                        t.id,
                        t.transaction_date.isoformat(),
                        t.post_date.isoformat() if t.post_date else "",
                        t.description,
                        account_map.get(t.account_id, ""),
                        t.bank_category or "",
                        category_map.get(t.category_id, "") if t.category_id else "",
                        (
                            category_map.get(t.auto_category_id, "")
                            if t.auto_category_id
                            else ""
                        ),
                        t.merchant_name or "",
                        t.auto_merchant_name or "",
                        t.amount / 100,
                        t.transaction_type,
                        t.data_import_id,
                        t.amortize_months or "",
                        (
                            t.amortize_end_date.isoformat()
                            if t.amortize_end_date
                            else ""
                        ),
                    ]
                )

        logger.info(f"✓ Successfully exported transactions to: {output_path}")

    except Exception as e:
        logger.error(f"Error exporting transactions: {e}")
        sys.exit(1)


def cmd_update_from_csv(args, db_manager, config):
    """Update transactions from a CSV file.

    Args:
        args: Parsed command-line arguments
        db_manager: Database manager instance
        config: Application configuration
    """
    csv_path = Path(args.input)
    if not csv_path.exists():
        logger.error(f"File not found: {args.input}")
        sys.exit(1)

    logger.info(f"Reading updates from: {csv_path}")

    try:
        result = IngestionService(db_manager, config).update_from_csv(csv_path)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except csv.Error as e:
        logger.error(f"Error reading CSV file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error updating transactions: {e}")
        sys.exit(1)

    if result["total_updated"] == 0 and result["skipped"] == 0:
        logger.info("No updates needed.")
        return

    logger.info(f"\nUpdating {result['total_updated']} transaction(s)...")
    logger.info(f"  Category manual updates: {result['category_updated']}")
    logger.info(f"  Category auto-accepted: {result['category_auto_accepted']}")
    logger.info(f"  Merchant manual updates: {result['merchant_updated']}")
    logger.info(f"  Merchant auto-accepted: {result['merchant_auto_accepted']}")
    logger.info(f"  Amortization updates: {result['amortization_updated']}")
    if result["skipped"] > 0:
        logger.info(f"  Skipped: {result['skipped']}")

    logger.info(f"\n✓ Successfully updated {result['total_updated']} transaction(s)")


def cmd_set_amortization(args, db_manager, config):
    """Set amortization for a transaction.

    Args:
        args: Parsed command-line arguments with transaction_id and months
        db_manager: Database manager instance
        config: Application configuration
    """
    from dateutil.relativedelta import relativedelta

    transactions_repo = TransactionRepository(db_manager)

    transaction_id = args.transaction_id
    months = args.months

    # Validate months
    if months < 1:
        logger.error("Months must be a positive integer")
        sys.exit(1)

    # Look up transaction
    transaction = transactions_repo.find(transaction_id)
    if not transaction:
        logger.error(f"Transaction with ID '{transaction_id}' not found.")
        sys.exit(1)

    # Calculate amortize_end_date using month-boundary convention:
    # - Give full month accrual to any month the transaction touches
    # - End on last day of month before the actual anniversary date
    # Example: Jan 15, 2024 + 12 months → Dec 31, 2024 (not Jan 15, 2025)
    amortize_end_date = transaction.transaction_date + relativedelta(
        months=months - 1, day=31
    )

    # Update transaction
    try:
        transaction.amortize_months = months
        transaction.amortize_end_date = amortize_end_date
        success = transactions_repo.update(
            transaction, ["amortize_months", "amortize_end_date"]
        )

        if not success:
            logger.error("Failed to update transaction.")
            sys.exit(1)

        logger.info("✓ Transaction amortization set successfully")
        logger.info(f"  Transaction: {transaction.description[:50]}...")
        logger.info(f"  Amount: ${transaction.amount / 100:.2f}")
        logger.info(f"  Amortize months: {months}")
        logger.info(
            f"  Amortization period: {transaction.transaction_date.isoformat()} to {amortize_end_date.isoformat()}"
        )
        logger.info(f"  Monthly amount: ${transaction.amount / months / 100:.2f}")

    except Exception as e:
        logger.error(f"Error updating transaction: {e}")
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

    # transactions set-category
    set_category_parser = transactions_subparsers.add_parser(
        "set-category",
        help="Set category for a transaction",
        description="Assign a user-defined category to a transaction",
    )
    set_category_parser.add_argument(
        "transaction_id",
        help="Transaction ID (SHA256 hash)",
    )
    set_category_parser.add_argument(
        "category",
        help="Category name or ID",
    )
    set_category_parser.set_defaults(func=cmd_set_category)

    # transactions export
    export_parser = transactions_subparsers.add_parser(
        "export",
        help="Export transactions to CSV",
        description="Export transactions to a CSV file with date filtering",
        epilog="""
Examples:
  # Export transactions for October 2025
  python -m cli transactions export --month 2025/10 --output transactions.csv

  # Export transactions for a date range
  python -m cli transactions export --start-date 2025/10/01 --end-date 2025/10/31 --output transactions.csv

  # Export transactions for a specific account
  python -m cli transactions export --month 2025/10 --account bofa_checking --output transactions.csv
        """,
    )

    # Date range options (mutually exclusive)
    date_group = export_parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument(
        "--month",
        help="Month to export in YYYY/MM format (e.g., 2025/10 for October 2025)",
    )
    date_group.add_argument(
        "--start-date",
        help="Start date in YYYY/MM/DD format (e.g., 2025/10/01). Must be used with --end-date",
    )

    export_parser.add_argument(
        "--end-date",
        help="End date in YYYY/MM/DD format (e.g., 2025/10/31). Must be used with --start-date",
    )

    export_parser.add_argument(
        "--account",
        help="Filter by account name (case-insensitive exact match)",
    )

    export_parser.add_argument(
        "--output",
        required=True,
        help="Output CSV file path",
    )

    export_parser.set_defaults(func=cmd_export)

    # transactions update-from-csv
    update_from_csv_parser = transactions_subparsers.add_parser(
        "update-from-csv",
        help="Update transactions from a CSV file",
        description="Update categories and amortization by reading from an exported CSV file",
        epilog="""
Examples:
  # Export transactions, edit, then update
  python -m cli transactions export --month 2025/10 --output transactions.csv
  # ... edit transactions.csv to add categories, merchant names, and amortization ...
  python -m cli transactions update-from-csv --input transactions.csv

Workflow:
  1. Export transactions to CSV
  2. Edit the CSV:
     - category_name: Add a category name to manually categorize
     - category_name: Leave empty to accept auto_category_name
     - merchant_name: Add a merchant name to manually set it
     - merchant_name: Leave empty to accept auto_merchant_name
     - amortize_months: Set to number of months to amortize over
  3. Run this command to apply the changes

Logic:
  - If category_name is filled → update category to that value
  - If category_name is empty → update category to auto_category (if available)
  - If merchant_name is filled → update merchant to that value
  - If merchant_name is empty → update merchant to auto_merchant (if available)
  - If amortize_months is set → calculate and update amortize_end_date
        """,
    )

    update_from_csv_parser.add_argument(
        "--input",
        required=True,
        help="Path to the CSV file with updates",
    )

    update_from_csv_parser.set_defaults(func=cmd_update_from_csv)

    # transactions set-amortization
    set_amortization_parser = transactions_subparsers.add_parser(
        "set-amortization",
        help="Set amortization for a transaction",
        description="Set the number of months to amortize a transaction over",
        epilog="""
Examples:
  # Amortize a $120 annual subscription over 12 months
  python -m cli transactions set-amortization <transaction_id> --months 12

  # This will calculate the end date and set amortize_months
  # Monthly amount = $120 / 12 = $10
        """,
    )
    set_amortization_parser.add_argument(
        "transaction_id",
        help="Transaction ID (SHA256 hash)",
    )
    set_amortization_parser.add_argument(
        "--months",
        type=int,
        required=True,
        help="Number of months to amortize over (must be positive)",
    )
    set_amortization_parser.set_defaults(func=cmd_set_amortization)
