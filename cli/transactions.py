#!/usr/bin/env python3

import sys
import csv
import gzip
import shutil
from pathlib import Path
from datetime import datetime
from ingestion import get_ingestion_module
from categorization import auto_categorize
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

        # Archive the CSV file if enabled
        archive_filename = None
        config = services.config
        if config.archive_enabled:
            # Create archive directory if it doesn't exist
            config.archive_dir.mkdir(parents=True, exist_ok=True)

            # Generate archive filename: {account_name}_{timestamp}_{original_filename}.gz
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            original_filename = csv_path.name
            archive_filename = f"{account.name}_{timestamp}_{original_filename}.gz"
            archive_path = config.archive_dir / archive_filename

            # Gzip and copy the file
            with open(csv_path, "rb") as f_in:
                with gzip.open(archive_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            logger.info(f"Archived CSV to: {archive_path}")

        # Create DataImport record
        data_import = services.data_imports.create(account.id, archive_filename)
        logger.info(f"Created data import record (ID: {data_import.id})")

        # Set data_import_id on all transactions
        for transaction in transactions:
            transaction.data_import_id = data_import.id

        # Bulk insert transactions
        inserted_count = services.transactions.bulk_create(transactions)

        logger.info(f"✓ Successfully inserted {inserted_count} transactions")

        if inserted_count < len(transactions):
            skipped = len(transactions) - inserted_count
            logger.info(f"  ({skipped} duplicate transaction(s) skipped)")

        # Auto-categorize newly inserted transactions
        # This should never fail the ingest process
        if inserted_count > 0:
            try:
                logger.info("\nRunning auto-categorization...")

                # Get historical transactions for training (last 90 days, manually categorized)
                historical_transactions = (
                    services.transactions.find_historical_for_categorization(
                        account.id, days=90
                    )
                )
                logger.info(
                    f"Found {len(historical_transactions)} historical categorized transactions"
                )

                # Get all available categories
                categories = services.categories.find_all()
                logger.info(f"Using {len(categories)} available categories")

                # Run auto-categorization
                categorized_transactions = auto_categorize(
                    transactions, categories, historical_transactions, services.config
                )

                # Update transactions with auto_category_id
                # Only update transactions that have auto_category_id set
                to_update = [
                    t
                    for t in categorized_transactions
                    if t.auto_category_id is not None
                ]

                if to_update:
                    updated_count = services.transactions.batch_update_auto_categories(
                        to_update
                    )
                    logger.info(f"✓ Auto-categorized {updated_count} transaction(s)")
                else:
                    logger.info("No transactions were auto-categorized")

            except Exception as e:
                # Log error but don't fail the ingest
                logger.warning(
                    f"Auto-categorization failed (ingest was successful): {e}"
                )

    except Exception as e:
        logger.error(f"Error during ingestion: {e}")
        sys.exit(1)


def cmd_set_category(args, services):
    """Set the category for a transaction.

    Args:
        args: Parsed command-line arguments with transaction_id and category
        services: Services container with transactions and categories services
    """
    transaction_id = args.transaction_id
    category_input = args.category

    # Look up transaction
    transaction = services.transactions.find(transaction_id)
    if not transaction:
        logger.error(f"Transaction with ID '{transaction_id}' not found.")
        sys.exit(1)

    # Look up category (try as ID first, then by name)
    category = None
    try:
        category_id = int(category_input)
        category = services.categories.find(category_id)
    except ValueError:
        # Not a number, try as category name
        category = services.categories.find_by_name(category_input)

    if not category:
        logger.error(f"Category '{category_input}' not found.")
        logger.info("Use 'python -m cli categories list' to see available categories.")
        sys.exit(1)

    # Update transaction category_id
    try:
        # We need to update the transaction in the database
        with services.db_manager.connect() as conn:
            cursor = conn.execute(
                "UPDATE transactions SET category_id = ? WHERE id = ?",
                (category.id, transaction_id),
            )
            conn.commit()

            if cursor.rowcount == 0:
                logger.error("Failed to update transaction.")
                sys.exit(1)

        logger.info("✓ Transaction categorized successfully")
        logger.info(f"  Transaction: {transaction.description[:50]}...")
        logger.info(f"  Category: {category.name}")

    except Exception as e:
        logger.error(f"Error updating transaction: {e}")
        sys.exit(1)


def cmd_export(args, services):
    """Export transactions to CSV.

    Args:
        args: Parsed command-line arguments
        services: Services container with transactions, accounts, categories services
    """
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
        account = services.accounts.find_by_name(args.account)
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
            transactions = services.transactions.get_transactions_by_month(
                year, month, account_id
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
            transactions = services.transactions.get_transactions_by_date_range(
                start_date, end_date, account_id
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
    accounts = services.accounts.find_all()
    categories = services.categories.find_all()

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
                    "amount",
                    "transaction_type",
                    "data_import_id",
                    "created_at",
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
                        float(t.amount),
                        t.type,
                        t.data_import_id,
                        "",  # created_at - not available on Transaction model
                    ]
                )

        logger.info(f"✓ Successfully exported transactions to: {output_path}")

    except Exception as e:
        logger.error(f"Error exporting transactions: {e}")
        sys.exit(1)


def cmd_update_categories_from_csv(args, services):
    """Update transaction categories from a CSV file.

    Args:
        args: Parsed command-line arguments
        services: Services container with transactions, categories services
    """
    # Validate CSV file exists
    csv_path = Path(args.input)
    if not csv_path.exists():
        logger.error(f"File not found: {args.input}")
        sys.exit(1)

    logger.info(f"Reading categories from: {csv_path}")

    # Load all categories for name-to-id mapping
    categories = services.categories.find_all()
    category_name_to_id = {cat.name: cat.id for cat in categories}

    # Read CSV file
    try:
        with open(csv_path, "r") as csvfile:
            reader = csv.DictReader(csvfile)

            # Validate headers
            expected_headers = {
                "id",
                "transaction_date",
                "post_date",
                "description",
                "account_name",
                "bank_category",
                "category_name",
                "auto_category_name",
                "amount",
                "transaction_type",
                "data_import_id",
                "created_at",
            }
            if not expected_headers.issubset(set(reader.fieldnames or [])):
                logger.error(
                    f"CSV file is missing required headers. Expected: {expected_headers}"
                )
                sys.exit(1)

            # Process each row
            transactions_to_update = []
            updated_count = 0
            accepted_auto_count = 0
            skipped_count = 0

            for row in reader:
                transaction_id = row["id"]
                category_name = row["category_name"].strip()
                auto_category_name = row["auto_category_name"].strip()

                # Fetch transaction from database
                transaction = services.transactions.find(transaction_id)
                if not transaction:
                    logger.warning(f"Transaction not found: {transaction_id}, skipping")
                    skipped_count += 1
                    continue

                # Determine what to update
                new_category_id = None

                if category_name:
                    # User provided a category - use it
                    if category_name not in category_name_to_id:
                        logger.warning(
                            f"Category '{category_name}' not found for transaction {transaction_id[:8]}..., skipping"
                        )
                        skipped_count += 1
                        continue
                    new_category_id = category_name_to_id[category_name]

                    # Only update if category has changed
                    if transaction.category_id != new_category_id:
                        transaction.category_id = new_category_id
                        transactions_to_update.append(transaction)
                        updated_count += 1
                else:
                    # No user category - accept auto category if available
                    if auto_category_name and transaction.auto_category_id:
                        # Only update if category_id is different from auto_category_id
                        if transaction.category_id != transaction.auto_category_id:
                            transaction.category_id = transaction.auto_category_id
                            transactions_to_update.append(transaction)
                            accepted_auto_count += 1

        if not transactions_to_update:
            logger.info("No category updates needed.")
            return

        logger.info(
            f"\nUpdating categories for {len(transactions_to_update)} transaction(s)..."
        )
        logger.info(f"  Manual updates: {updated_count}")
        logger.info(f"  Auto-category accepted: {accepted_auto_count}")
        if skipped_count > 0:
            logger.info(f"  Skipped: {skipped_count}")

        # Batch update
        updated = services.transactions.batch_update_categories(transactions_to_update)
        logger.info(f"\n✓ Successfully updated {updated} transaction(s)")

    except csv.Error as e:
        logger.error(f"Error reading CSV file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error updating categories: {e}")
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

    # transactions update-categories-from-csv
    update_categories_parser = transactions_subparsers.add_parser(
        "update-categories-from-csv",
        help="Update transaction categories from a CSV file",
        description="Update categories by reading from an exported CSV file",
        epilog="""
Examples:
  # Export transactions, edit categories, then update
  python -m cli transactions export --month 2025/10 --output transactions.csv
  # ... edit transactions.csv to add categories ...
  python -m cli transactions update-categories-from-csv --input transactions.csv

Workflow:
  1. Export transactions to CSV
  2. Edit the category_name column in the CSV:
     - Add a category name to manually categorize a transaction
     - Leave empty to accept the auto_category_name
  3. Run this command to apply the changes

Logic:
  - If category_name is filled → update category to that value
  - If category_name is empty → update category to auto_category (if available)
        """,
    )

    update_categories_parser.add_argument(
        "--input",
        required=True,
        help="Path to the CSV file with updated categories",
    )

    update_categories_parser.set_defaults(func=cmd_update_categories_from_csv)
