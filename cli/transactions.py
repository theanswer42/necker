#!/usr/bin/env python3

import sys
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
                    transactions, categories, historical_transactions
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
