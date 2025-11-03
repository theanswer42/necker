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

                # Update transactions with auto_category_id and auto_merchant_name
                # Only update transactions that have either field set
                to_update = [
                    t
                    for t in categorized_transactions
                    if t.auto_category_id is not None
                    or t.auto_merchant_name is not None
                ]

                if to_update:
                    updated_count = services.transactions.batch_update(
                        to_update, ["auto_category_id", "auto_merchant_name"]
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
        transaction.category_id = category.id
        success = services.transactions.update(transaction, ["category_id"])

        if not success:
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
                    "merchant_name",
                    "auto_merchant_name",
                    "amount",
                    "transaction_type",
                    "data_import_id",
                    "created_at",
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
                        float(t.amount),
                        t.type,
                        t.data_import_id,
                        "",  # created_at - not available on Transaction model
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


def cmd_update_from_csv(args, services):
    """Update transactions from a CSV file.

    Args:
        args: Parsed command-line arguments
        services: Services container with transactions, categories services
    """
    from dateutil.relativedelta import relativedelta

    # Validate CSV file exists
    csv_path = Path(args.input)
    if not csv_path.exists():
        logger.error(f"File not found: {args.input}")
        sys.exit(1)

    logger.info(f"Reading updates from: {csv_path}")

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
                "merchant_name",
                "auto_merchant_name",
                "amount",
                "transaction_type",
                "data_import_id",
                "created_at",
                "amortize_months",
                "amortize_end_date",
            }
            if not expected_headers.issubset(set(reader.fieldnames or [])):
                logger.error(
                    f"CSV file is missing required headers. Expected: {expected_headers}"
                )
                sys.exit(1)

            # Process each row
            category_updates = []
            merchant_updates = []
            amortization_updates = []
            category_updated_count = 0
            accepted_auto_count = 0
            merchant_updated_count = 0
            accepted_auto_merchant_count = 0
            amortization_updated_count = 0
            skipped_count = 0

            for row in reader:
                transaction_id = row["id"]
                category_name = row["category_name"].strip()
                auto_category_name = row["auto_category_name"].strip()
                merchant_name = row["merchant_name"].strip()
                auto_merchant_name = row["auto_merchant_name"].strip()
                amortize_months_str = row["amortize_months"].strip()

                # Fetch transaction from database
                transaction = services.transactions.find(transaction_id)
                if not transaction:
                    logger.warning(f"Transaction not found: {transaction_id}, skipping")
                    skipped_count += 1
                    continue

                # Process category updates
                new_category_id = None
                category_changed = False

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
                        category_updates.append(transaction)
                        category_updated_count += 1
                        category_changed = True
                else:
                    # No user category - accept auto category if available
                    if auto_category_name and transaction.auto_category_id:
                        # Only update if category_id is different from auto_category_id
                        if transaction.category_id != transaction.auto_category_id:
                            transaction.category_id = transaction.auto_category_id
                            category_updates.append(transaction)
                            accepted_auto_count += 1
                            category_changed = True

                # Process merchant name updates
                merchant_changed = False

                if merchant_name:
                    # User provided a merchant name - use it
                    # Only update if merchant_name has changed
                    if transaction.merchant_name != merchant_name:
                        transaction.merchant_name = merchant_name
                        # Only add if not already in category_updates
                        if not category_changed:
                            merchant_updates.append(transaction)
                        merchant_updated_count += 1
                        merchant_changed = True
                else:
                    # No user merchant name - accept auto merchant name if available
                    if auto_merchant_name and transaction.auto_merchant_name:
                        # Only update if merchant_name is different from auto_merchant_name
                        if transaction.merchant_name != transaction.auto_merchant_name:
                            transaction.merchant_name = transaction.auto_merchant_name
                            # Only add if not already in other update lists
                            if not category_changed and not merchant_changed:
                                merchant_updates.append(transaction)
                            accepted_auto_merchant_count += 1
                            merchant_changed = True

                # Process amortization updates
                if amortize_months_str:
                    try:
                        amortize_months = int(amortize_months_str)
                        if amortize_months < 1:
                            logger.warning(
                                f"Invalid amortize_months {amortize_months} for transaction {transaction_id[:8]}..., skipping"
                            )
                            continue

                        # Check if amortization has changed
                        if transaction.amortize_months != amortize_months:
                            # Calculate new amortize_end_date using month-boundary convention
                            # End on last day of month before the actual anniversary date
                            amortize_end_date = (
                                transaction.transaction_date
                                + relativedelta(months=amortize_months - 1, day=31)
                            )

                            # Update fields
                            transaction.amortize_months = amortize_months
                            transaction.amortize_end_date = amortize_end_date

                            # Only add if not already in category_updates or merchant_updates
                            if not category_changed and not merchant_changed:
                                amortization_updates.append(transaction)
                            amortization_updated_count += 1
                    except ValueError:
                        logger.warning(
                            f"Invalid amortize_months value '{amortize_months_str}' for transaction {transaction_id[:8]}..., skipping"
                        )

        # Combine updates
        all_updates = category_updates + merchant_updates + amortization_updates

        if not all_updates:
            logger.info("No updates needed.")
            return

        logger.info(f"\nUpdating {len(all_updates)} transaction(s)...")
        logger.info(f"  Category manual updates: {category_updated_count}")
        logger.info(f"  Category auto-accepted: {accepted_auto_count}")
        logger.info(f"  Merchant manual updates: {merchant_updated_count}")
        logger.info(f"  Merchant auto-accepted: {accepted_auto_merchant_count}")
        logger.info(f"  Amortization updates: {amortization_updated_count}")
        if skipped_count > 0:
            logger.info(f"  Skipped: {skipped_count}")

        # Batch update categories
        if category_updates:
            updated = services.transactions.batch_update(
                category_updates, ["category_id"]
            )
            logger.info(
                f"\n✓ Successfully updated categories for {updated} transaction(s)"
            )

        # Update merchant names
        if merchant_updates:
            updated = services.transactions.batch_update(
                merchant_updates, ["merchant_name"]
            )
            logger.info(
                f"✓ Successfully updated merchant names for {updated} transaction(s)"
            )

        # Update amortization
        if amortization_updates:
            updated = services.transactions.batch_update(
                amortization_updates, ["amortize_months", "amortize_end_date"]
            )
            logger.info(
                f"✓ Successfully updated amortization for {updated} transaction(s)"
            )

    except csv.Error as e:
        logger.error(f"Error reading CSV file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error updating transactions: {e}")
        sys.exit(1)


def cmd_set_amortization(args, services):
    """Set amortization for a transaction.

    Args:
        args: Parsed command-line arguments with transaction_id and months
        services: Services container with transactions service
    """
    from dateutil.relativedelta import relativedelta

    transaction_id = args.transaction_id
    months = args.months

    # Validate months
    if months < 1:
        logger.error("Months must be a positive integer")
        sys.exit(1)

    # Look up transaction
    transaction = services.transactions.find(transaction_id)
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
        success = services.transactions.update(
            transaction, ["amortize_months", "amortize_end_date"]
        )

        if not success:
            logger.error("Failed to update transaction.")
            sys.exit(1)

        logger.info("✓ Transaction amortization set successfully")
        logger.info(f"  Transaction: {transaction.description[:50]}...")
        logger.info(f"  Amount: ${transaction.amount}")
        logger.info(f"  Amortize months: {months}")
        logger.info(
            f"  Amortization period: {transaction.transaction_date.isoformat()} to {amortize_end_date.isoformat()}"
        )
        logger.info(f"  Monthly amount: ${float(transaction.amount) / months:.2f}")

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
