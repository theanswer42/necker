"""Tests for the ingestion service."""

import csv
import pytest
from datetime import date
from pathlib import Path

from services.ingestion import ingest_csv, update_from_csv


def _make_bofa_csv(
    tmp_path: Path, rows: list[list[str]], filename: str = "test.csv"
) -> Path:
    """Create a BofA-format CSV file for testing."""
    csv_path = tmp_path / filename
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        # BofA summary section (5 lines)
        writer.writerow(["Description", "", "Summary Amt."])
        writer.writerow(["Beginning balance as of 01/01/2024", "", "1000.00"])
        writer.writerow(["Total credits", "", "500.00"])
        writer.writerow(["Total debits", "", "-200.00"])
        writer.writerow(["Ending balance as of 01/31/2024", "", "1300.00"])
        writer.writerow([])  # empty line
        writer.writerow(["Date", "Description", "Amount", "Running Bal."])
        for row in rows:
            writer.writerow(row)
    return csv_path


def _make_export_csv(
    tmp_path: Path, rows: list[dict], filename: str = "export.csv"
) -> Path:
    """Create an export-format CSV file for testing."""
    csv_path = tmp_path / filename
    fieldnames = [
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
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            full_row = {k: "" for k in fieldnames}
            full_row.update(row)
            writer.writerow(full_row)
    return csv_path


class TestIngestCsv:
    """Tests for ingest_csv service function."""

    def test_basic_ingest(self, services, tmp_path):
        """Test ingesting a simple CSV file."""
        account = services.accounts.create("test_account", "bofa", "Test Account")

        csv_path = _make_bofa_csv(
            tmp_path,
            [
                ["01/15/2024", "Coffee Shop", "-5.00", "995.00"],
                ["01/20/2024", "Salary", "2000.00", "2995.00"],
            ],
        )

        result = ingest_csv(csv_path, account, services)

        assert result["parsed"] == 2
        assert result["inserted"] == 2
        assert result["skipped"] == 0
        assert result["categorized"] == 0
        assert result["data_import_id"] is not None
        assert result["archive_filename"] is None  # archiving disabled in test config

        # Verify transactions are in DB
        transactions = services.transactions.find_by_account(account.id)
        assert len(transactions) == 2

    def test_ingest_empty_csv(self, services, tmp_path):
        """Test ingesting a CSV with no transactions."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        csv_path = _make_bofa_csv(tmp_path, [])

        result = ingest_csv(csv_path, account, services)

        assert result["parsed"] == 0
        assert result["inserted"] == 0
        assert result["skipped"] == 0
        assert result["categorized"] == 0

    def test_ingest_deduplication(self, services, tmp_path):
        """Test that duplicate transactions are skipped on re-import."""
        account = services.accounts.create("test_account", "bofa", "Test Account")

        csv_path = _make_bofa_csv(
            tmp_path,
            [
                ["01/15/2024", "Coffee Shop", "-5.00", "995.00"],
            ],
        )

        # First import
        result1 = ingest_csv(csv_path, account, services)
        assert result1["inserted"] == 1
        assert result1["skipped"] == 0

        # Second import of same file
        result2 = ingest_csv(csv_path, account, services)
        assert result2["parsed"] == 1
        assert result2["inserted"] == 0
        assert result2["skipped"] == 1

        # Only one transaction in DB
        transactions = services.transactions.find_by_account(account.id)
        assert len(transactions) == 1

    def test_ingest_invalid_account_type(self, services, tmp_path):
        """Test that unknown account type raises ValueError."""
        account = services.accounts.create(
            "test_account", "unknown_bank", "Test Account"
        )
        csv_path = _make_bofa_csv(
            tmp_path,
            [
                ["01/15/2024", "Coffee", "-5.00", "995.00"],
            ],
        )

        with pytest.raises(ValueError):
            ingest_csv(csv_path, account, services)

    def test_ingest_creates_data_import_record(self, services, tmp_path):
        """Test that a DataImport record is created for each ingest."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        csv_path = _make_bofa_csv(
            tmp_path,
            [
                ["01/15/2024", "Coffee", "-5.00", "995.00"],
            ],
        )

        result = ingest_csv(csv_path, account, services)

        data_import = services.data_imports.find(result["data_import_id"])
        assert data_import is not None
        assert data_import.account_id == account.id

    def test_ingest_with_archiving(self, services, tmp_path):
        """Test that CSV is archived when archiving is enabled."""
        from config import Config

        archive_dir = tmp_path / "archives"
        config = Config(
            base_dir=tmp_path,
            db_data_dir=tmp_path / "db",
            db_filename="test.db",
            log_level="DEBUG",
            log_dir=tmp_path / "logs",
            archive_enabled=True,
            archive_dir=archive_dir,
            enable_reset=False,
            llm_enabled=False,
            llm_provider="openai",
            llm_openai_api_key="",
            llm_openai_model="gpt-4o-mini",
        )
        services.config = config

        account = services.accounts.create("test_account", "bofa", "Test Account")
        csv_path = _make_bofa_csv(
            tmp_path,
            [
                ["01/15/2024", "Coffee", "-5.00", "995.00"],
            ],
        )

        result = ingest_csv(csv_path, account, services)

        assert result["archive_filename"] is not None
        assert (archive_dir / result["archive_filename"]).exists()

        # Restore config
        services.config = services.config


class TestUpdateFromCsv:
    """Tests for update_from_csv service function."""

    def _create_transaction(self, services, account, description, amount, data_import):
        """Helper to create a transaction for testing."""
        from models.transaction import Transaction

        t = Transaction.create_with_checksum(
            raw_data=f"01/15/2024,{description},{amount},1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description=description,
            bank_category=None,
            amount=abs(int(float(amount) * 100)),
            transaction_type="expense" if float(amount) < 0 else "income",
        )
        t.data_import_id = data_import.id
        services.transactions.create(t)
        return t

    def test_update_category(self, services, tmp_path):
        """Test updating a transaction's category via CSV."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, None)
        category = services.categories.create("Food", "Food expenses")
        txn = self._create_transaction(
            services, account, "Coffee", "-5.00", data_import
        )

        csv_path = _make_export_csv(
            tmp_path,
            [
                {
                    "id": txn.id,
                    "transaction_date": "2024-01-15",
                    "description": txn.description,
                    "category_name": "Food",
                    "amount": "-5.00",
                    "transaction_type": "expense",
                }
            ],
        )

        result = update_from_csv(csv_path, services)

        assert result["category_updated"] == 1
        assert result["total_updated"] == 1

        updated = services.transactions.find(txn.id)
        assert updated.category_id == category.id

    def test_accept_auto_category(self, services, tmp_path):
        """Test accepting auto-category when no manual category is given."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, None)
        category = services.categories.create("Food", "Food expenses")
        txn = self._create_transaction(
            services, account, "Coffee", "-5.00", data_import
        )

        # Set auto_category_id on transaction
        txn.auto_category_id = category.id
        services.transactions.update(txn, ["auto_category_id"])

        csv_path = _make_export_csv(
            tmp_path,
            [
                {
                    "id": txn.id,
                    "transaction_date": "2024-01-15",
                    "description": txn.description,
                    "category_name": "",  # no manual category
                    "auto_category_name": "Food",
                    "amount": "-5.00",
                    "transaction_type": "expense",
                }
            ],
        )

        result = update_from_csv(csv_path, services)

        assert result["category_auto_accepted"] == 1
        assert result["total_updated"] == 1

        updated = services.transactions.find(txn.id)
        assert updated.category_id == category.id

    def test_update_merchant_name(self, services, tmp_path):
        """Test updating a transaction's merchant name via CSV."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, None)
        txn = self._create_transaction(
            services, account, "SBUX #1234", "-5.00", data_import
        )

        csv_path = _make_export_csv(
            tmp_path,
            [
                {
                    "id": txn.id,
                    "transaction_date": "2024-01-15",
                    "description": txn.description,
                    "merchant_name": "Starbucks",
                    "amount": "-5.00",
                    "transaction_type": "expense",
                }
            ],
        )

        result = update_from_csv(csv_path, services)

        assert result["merchant_updated"] == 1
        assert result["total_updated"] == 1

        updated = services.transactions.find(txn.id)
        assert updated.merchant_name == "Starbucks"

    def test_update_amortization(self, services, tmp_path):
        """Test setting amortization via CSV."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, None)
        txn = self._create_transaction(
            services, account, "Annual Sub", "-120.00", data_import
        )

        csv_path = _make_export_csv(
            tmp_path,
            [
                {
                    "id": txn.id,
                    "transaction_date": "2024-01-15",
                    "description": txn.description,
                    "amount": "-120.00",
                    "transaction_type": "expense",
                    "amortize_months": "12",
                }
            ],
        )

        result = update_from_csv(csv_path, services)

        assert result["amortization_updated"] == 1
        assert result["total_updated"] == 1

        updated = services.transactions.find(txn.id)
        assert updated.amortize_months == 12
        assert updated.amortize_end_date is not None

    def test_skip_unknown_transaction(self, services, tmp_path):
        """Test that rows with unknown transaction IDs are skipped."""
        services.accounts.create("test_account", "bofa", "Test Account")

        csv_path = _make_export_csv(
            tmp_path,
            [
                {
                    "id": "nonexistent_id_" + "x" * 48,
                    "transaction_date": "2024-01-15",
                    "description": "Unknown",
                    "category_name": "Food",
                    "amount": "-5.00",
                    "transaction_type": "expense",
                }
            ],
        )

        result = update_from_csv(csv_path, services)

        assert result["skipped"] == 1
        assert result["total_updated"] == 0

    def test_skip_unknown_category(self, services, tmp_path):
        """Test that rows with unknown category names are skipped."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, None)
        txn = self._create_transaction(
            services, account, "Coffee", "-5.00", data_import
        )

        csv_path = _make_export_csv(
            tmp_path,
            [
                {
                    "id": txn.id,
                    "transaction_date": "2024-01-15",
                    "description": txn.description,
                    "category_name": "NonExistentCategory",
                    "amount": "-5.00",
                    "transaction_type": "expense",
                }
            ],
        )

        result = update_from_csv(csv_path, services)

        assert result["skipped"] == 1
        assert result["total_updated"] == 0

    def test_no_updates_needed(self, services, tmp_path):
        """Test result when CSV has no changes to apply."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, None)
        txn = self._create_transaction(
            services, account, "Coffee", "-5.00", data_import
        )

        csv_path = _make_export_csv(
            tmp_path,
            [
                {
                    "id": txn.id,
                    "transaction_date": "2024-01-15",
                    "description": txn.description,
                    "amount": "-5.00",
                    "transaction_type": "expense",
                }
            ],
        )

        result = update_from_csv(csv_path, services)

        assert result["total_updated"] == 0
        assert result["skipped"] == 0

    def test_invalid_headers_raises(self, services, tmp_path):
        """Test that CSV with missing headers raises ValueError."""
        csv_path = tmp_path / "bad.csv"
        with open(csv_path, "w") as f:
            f.write("wrong,headers\n")
            f.write("a,b\n")

        with pytest.raises(ValueError, match="missing required headers"):
            update_from_csv(csv_path, services)

    def test_multiple_updates_same_transaction(self, services, tmp_path):
        """Test that category and merchant can be updated in the same row."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, None)
        category = services.categories.create("Food", "Food expenses")
        txn = self._create_transaction(
            services, account, "SBUX #1234", "-5.00", data_import
        )

        csv_path = _make_export_csv(
            tmp_path,
            [
                {
                    "id": txn.id,
                    "transaction_date": "2024-01-15",
                    "description": txn.description,
                    "category_name": "Food",
                    "merchant_name": "Starbucks",
                    "amount": "-5.00",
                    "transaction_type": "expense",
                }
            ],
        )

        result = update_from_csv(csv_path, services)

        assert result["category_updated"] == 1
        assert result["merchant_updated"] == 1
        assert result["total_updated"] == 1

        updated = services.transactions.find(txn.id)
        assert updated.category_id == category.id
        assert updated.merchant_name == "Starbucks"
