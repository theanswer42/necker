"""Ingestion service for importing and updating transactions."""

import gzip
import shutil
from datetime import datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta

from config import Config
from ingestion import get_ingestion_module
from models.account import Account
from repositories.categories import CategoryRepository
from repositories.data_imports import DataImportRepository
from repositories.transactions import TransactionRepository
from services.categorization import auto_categorize


class IngestionService:
    """Handles CSV import, archiving, and auto-categorization."""

    def __init__(self, db_manager, config: Config):
        self.config = config
        self.transactions = TransactionRepository(db_manager)
        self.data_imports = DataImportRepository(db_manager)
        self.categories = CategoryRepository(db_manager)

    def ingest_csv(self, csv_path: Path, account: Account) -> dict:
        """Ingest transactions from a CSV file for an account.

        Handles ingestion module lookup, CSV parsing, optional archiving,
        DataImport record creation, bulk insert, and auto-categorization.

        Args:
            csv_path: Path to the CSV file to ingest.
            account: The account to import transactions for.

        Returns:
            Dictionary with keys:
            - "parsed": number of transactions parsed from CSV
            - "inserted": number of transactions inserted into DB
            - "skipped": number of duplicate transactions skipped
            - "categorized": number of transactions auto-categorized

        Raises:
            ValueError: If no ingestion module is found for the account type.
            Exception: If CSV reading or DB insert fails.
        """
        ingestion_module = get_ingestion_module(account.account_type)

        with open(csv_path, "r") as f:
            transactions = ingestion_module.ingest(f, account.id)

        parsed_count = len(transactions)

        if not transactions:
            return {"parsed": 0, "inserted": 0, "skipped": 0, "categorized": 0}

        # Archive the CSV file if enabled
        archive_filename = None
        if self.config.archive_enabled:
            self.config.archive_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_filename = f"{account.name}_{timestamp}_{csv_path.name}.gz"
            archive_path = self.config.archive_dir / archive_filename
            with open(csv_path, "rb") as f_in:
                with gzip.open(archive_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

        # Create DataImport record and link transactions to it
        data_import = self.data_imports.create(account.id, archive_filename)
        for transaction in transactions:
            transaction.data_import_id = data_import.id

        # Bulk insert
        inserted_count = self.transactions.bulk_create(transactions)
        skipped_count = parsed_count - inserted_count

        # Auto-categorize newly inserted transactions
        categorized_count = 0
        if inserted_count > 0:
            historical = self.transactions.find_historical_for_categorization(
                account.id, limit=200
            )
            categories = self.categories.find_all()
            categorized_transactions = auto_categorize(
                transactions, categories, historical, self.config
            )
            to_update = [
                t
                for t in categorized_transactions
                if t.auto_category_id is not None or t.auto_merchant_name is not None
            ]
            if to_update:
                categorized_count = self.transactions.batch_update(
                    to_update, ["auto_category_id", "auto_merchant_name"]
                )

        return {
            "parsed": parsed_count,
            "inserted": inserted_count,
            "skipped": skipped_count,
            "categorized": categorized_count,
            "data_import_id": data_import.id,
            "archive_filename": archive_filename,
        }

    def update_from_csv(self, csv_path: Path) -> dict:
        """Update transactions from an exported/edited CSV file.

        Reads category, merchant, and amortization changes from a CSV and
        applies them to matching transactions in the database.

        Args:
            csv_path: Path to the CSV file with updates.

        Returns:
            Dictionary with keys:
            - "category_updated": manual category updates applied
            - "category_auto_accepted": auto-category accepted as manual category
            - "merchant_updated": manual merchant name updates applied
            - "merchant_auto_accepted": auto-merchant accepted as manual merchant
            - "amortization_updated": amortization updates applied
            - "skipped": rows skipped due to missing transaction or invalid data
            - "total_updated": total distinct transactions updated in the DB
        """
        import csv

        categories = self.categories.find_all()
        category_name_to_id = {cat.name: cat.id for cat in categories}

        with open(csv_path, "r") as csvfile:
            reader = csv.DictReader(csvfile)

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
                "amortize_months",
                "amortize_end_date",
            }
            if not expected_headers.issubset(set(reader.fieldnames or [])):
                raise ValueError(
                    f"CSV file is missing required headers. Expected: {expected_headers}"
                )

            transactions_to_update: dict[str, tuple] = {}
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

                transaction = self.transactions.find(transaction_id)
                if not transaction:
                    skipped_count += 1
                    continue

                # Process category updates
                if category_name:
                    if category_name not in category_name_to_id:
                        skipped_count += 1
                        continue
                    new_category_id = category_name_to_id[category_name]
                    if transaction.category_id != new_category_id:
                        transaction.category_id = new_category_id
                        if transaction_id not in transactions_to_update:
                            transactions_to_update[transaction_id] = (
                                transaction,
                                set(),
                            )
                        transactions_to_update[transaction_id][1].add("category_id")
                        category_updated_count += 1
                else:
                    if auto_category_name and transaction.auto_category_id:
                        if transaction.category_id != transaction.auto_category_id:
                            transaction.category_id = transaction.auto_category_id
                            if transaction_id not in transactions_to_update:
                                transactions_to_update[transaction_id] = (
                                    transaction,
                                    set(),
                                )
                            transactions_to_update[transaction_id][1].add("category_id")
                            accepted_auto_count += 1

                # Process merchant name updates
                if merchant_name:
                    if transaction.merchant_name != merchant_name:
                        transaction.merchant_name = merchant_name
                        if transaction_id not in transactions_to_update:
                            transactions_to_update[transaction_id] = (
                                transaction,
                                set(),
                            )
                        transactions_to_update[transaction_id][1].add("merchant_name")
                        merchant_updated_count += 1
                else:
                    if auto_merchant_name and transaction.auto_merchant_name:
                        if transaction.merchant_name != transaction.auto_merchant_name:
                            transaction.merchant_name = transaction.auto_merchant_name
                            if transaction_id not in transactions_to_update:
                                transactions_to_update[transaction_id] = (
                                    transaction,
                                    set(),
                                )
                            transactions_to_update[transaction_id][1].add(
                                "merchant_name"
                            )
                            accepted_auto_merchant_count += 1

                # Process amortization updates
                if amortize_months_str:
                    try:
                        amortize_months = int(amortize_months_str)
                        if amortize_months < 1:
                            skipped_count += 1
                            continue
                        if transaction.amortize_months != amortize_months:
                            amortize_end_date = (
                                transaction.transaction_date
                                + relativedelta(months=amortize_months - 1, day=31)
                            )
                            transaction.amortize_months = amortize_months
                            transaction.amortize_end_date = amortize_end_date
                            if transaction_id not in transactions_to_update:
                                transactions_to_update[transaction_id] = (
                                    transaction,
                                    set(),
                                )
                            transactions_to_update[transaction_id][1].add(
                                "amortize_months"
                            )
                            transactions_to_update[transaction_id][1].add(
                                "amortize_end_date"
                            )
                            amortization_updated_count += 1
                    except ValueError:
                        pass  # Invalid value — skip silently (not a skipped row)

        total_updated = 0
        for _txn_id, (transaction, fields_to_update) in transactions_to_update.items():
            total_updated += self.transactions.batch_update(
                [transaction], list(fields_to_update)
            )

        return {
            "category_updated": category_updated_count,
            "category_auto_accepted": accepted_auto_count,
            "merchant_updated": merchant_updated_count,
            "merchant_auto_accepted": accepted_auto_merchant_count,
            "amortization_updated": amortization_updated_count,
            "skipped": skipped_count,
            "total_updated": total_updated,
        }
