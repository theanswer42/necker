"""Tests for CLI transaction commands."""

import csv
import pytest
from argparse import Namespace
from datetime import date
from pathlib import Path

from models.transaction import Transaction
from cli.transactions import (
    cmd_ingest,
    cmd_set_category,
    cmd_export,
    cmd_set_amortization,
)


def _make_bofa_csv(tmp_path: Path, rows: list, filename: str = "test.csv") -> Path:
    csv_path = tmp_path / filename
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Description", "", "Summary Amt."])
        writer.writerow(["Beginning balance as of 01/01/2024", "", "1000.00"])
        writer.writerow(["Total credits", "", "500.00"])
        writer.writerow(["Total debits", "", "-200.00"])
        writer.writerow(["Ending balance as of 01/31/2024", "", "1300.00"])
        writer.writerow([])
        writer.writerow(["Date", "Description", "Amount", "Running Bal."])
        for row in rows:
            writer.writerow(row)
    return csv_path


def _make_transaction(services, account, description="Coffee", amount=500):
    data_import = services.data_imports.create(account.id, None)
    t = Transaction.create_with_checksum(
        raw_data=f"01/15/2024,{description},-5.00,995.00",
        account_id=account.id,
        transaction_date=date(2024, 1, 15),
        post_date=None,
        description=description,
        bank_category=None,
        amount=amount,
        transaction_type="expense",
    )
    t.data_import_id = data_import.id
    services.transactions.create(t)
    return t


class TestCmdIngest:
    """Tests for cmd_ingest."""

    def test_missing_csv_file_exits(self, services, tmp_path, output):
        args = Namespace(
            csv_file=str(tmp_path / "nonexistent.csv"), account_name="acct"
        )
        with pytest.raises(SystemExit) as exc:
            cmd_ingest(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_unknown_account_exits(self, services, tmp_path, output):
        csv_path = _make_bofa_csv(tmp_path, [])
        args = Namespace(csv_file=str(csv_path), account_name="no_such_account")
        with pytest.raises(SystemExit) as exc:
            cmd_ingest(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_invalid_account_type_exits(self, services, tmp_path, output):
        services.accounts.create("acct", "unknown_bank", "Test")
        csv_path = _make_bofa_csv(
            tmp_path, [["01/15/2024", "Coffee", "-5.00", "995.00"]]
        )
        args = Namespace(csv_file=str(csv_path), account_name="acct")
        with pytest.raises(SystemExit) as exc:
            cmd_ingest(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_successful_ingest(self, services, tmp_path, output):
        services.accounts.create("acct", "bofa", "Test Account")
        csv_path = _make_bofa_csv(
            tmp_path,
            [
                ["01/15/2024", "Coffee", "-5.00", "995.00"],
            ],
        )
        args = Namespace(csv_file=str(csv_path), account_name="acct")
        cmd_ingest(
            args, services.db_manager, services.config, output
        )  # should not raise
        account = services.accounts.find_by_name("acct")
        txns = services.transactions.find_by_account(account.id)
        assert len(txns) == 1

    def test_empty_csv_returns_normally(self, services, tmp_path, output):
        services.accounts.create("acct", "bofa", "Test Account")
        csv_path = _make_bofa_csv(tmp_path, [])
        args = Namespace(csv_file=str(csv_path), account_name="acct")
        cmd_ingest(
            args, services.db_manager, services.config, output
        )  # should not raise or exit


class TestCmdSetCategory:
    """Tests for cmd_set_category."""

    def test_unknown_transaction_exits(self, services, output):
        args = Namespace(transaction_id="nonexistent" * 4, category="Food")
        with pytest.raises(SystemExit) as exc:
            cmd_set_category(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_unknown_category_name_exits(self, services, output):
        account = services.accounts.create("acct", "bofa", "Test")
        txn = _make_transaction(services, account)
        args = Namespace(transaction_id=txn.id, category="NoSuchCategory")
        with pytest.raises(SystemExit) as exc:
            cmd_set_category(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_set_category_by_name(self, services, output):
        account = services.accounts.create("acct", "bofa", "Test")
        category = services.categories.create("Food", "Food expenses")
        txn = _make_transaction(services, account)
        args = Namespace(transaction_id=txn.id, category="Food")
        cmd_set_category(args, services.db_manager, services.config, output)
        updated = services.transactions.find(txn.id)
        assert updated.category_id == category.id

    def test_set_category_by_id(self, services, output):
        account = services.accounts.create("acct", "bofa", "Test")
        category = services.categories.create("Food", "Food expenses")
        txn = _make_transaction(services, account)
        args = Namespace(transaction_id=txn.id, category=str(category.id))
        cmd_set_category(args, services.db_manager, services.config, output)
        updated = services.transactions.find(txn.id)
        assert updated.category_id == category.id


class TestCmdExport:
    """Tests for cmd_export."""

    def _base_args(
        self, output_path, month=None, start_date=None, end_date=None, account=None
    ):
        return Namespace(
            month=month,
            start_date=start_date,
            end_date=end_date,
            account=account,
            output=str(output_path),
        )

    def test_start_date_without_end_date_exits(self, services, tmp_path, output):
        args = self._base_args(tmp_path / "out.csv", start_date="2024/01/01")
        with pytest.raises(SystemExit) as exc:
            cmd_export(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_end_date_without_start_date_exits(self, services, tmp_path, output):
        args = self._base_args(tmp_path / "out.csv", end_date="2024/01/31")
        with pytest.raises(SystemExit) as exc:
            cmd_export(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_invalid_month_format_exits(self, services, tmp_path, output):
        args = self._base_args(tmp_path / "out.csv", month="not-a-month")
        with pytest.raises(SystemExit) as exc:
            cmd_export(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_month_out_of_range_exits(self, services, tmp_path, output):
        args = self._base_args(tmp_path / "out.csv", month="2024/13")
        with pytest.raises(SystemExit) as exc:
            cmd_export(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_no_transactions_exits_0(self, services, tmp_path, output):
        args = self._base_args(tmp_path / "out.csv", month="2024/01")
        with pytest.raises(SystemExit) as exc:
            cmd_export(args, services.db_manager, services.config, output)
        assert exc.value.code == 0

    def test_export_by_month_writes_csv(self, services, tmp_path, output):
        account = services.accounts.create("acct", "bofa", "Test")
        category = services.categories.create("Food", "Food")
        txn = _make_transaction(services, account)
        txn.category_id = category.id
        services.transactions.update(txn, ["category_id"])

        out = tmp_path / "out.csv"
        args = self._base_args(out, month="2024/01")
        cmd_export(args, services.db_manager, services.config, output)

        assert out.exists()
        with open(out) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["description"] == "Coffee"
        assert rows[0]["category_name"] == "Food"
        assert rows[0]["amount"] == "5.0"

    def test_export_by_date_range_writes_csv(self, services, tmp_path, output):
        account = services.accounts.create("acct", "bofa", "Test")
        _make_transaction(services, account)

        out = tmp_path / "out.csv"
        args = self._base_args(out, start_date="2024/01/01", end_date="2024/01/31")
        cmd_export(args, services.db_manager, services.config, output)

        assert out.exists()
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1

    def test_export_with_unknown_account_filter_exits(self, services, tmp_path, output):
        out = tmp_path / "out.csv"
        args = self._base_args(out, month="2024/01", account="no_such_account")
        with pytest.raises(SystemExit) as exc:
            cmd_export(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_export_csv_headers(self, services, tmp_path, output):
        account = services.accounts.create("acct", "bofa", "Test")
        _make_transaction(services, account)

        out = tmp_path / "out.csv"
        args = self._base_args(out, month="2024/01")
        cmd_export(args, services.db_manager, services.config, output)

        with open(out) as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
        expected = [
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
        assert headers == expected


class TestCmdSetAmortization:
    """Tests for cmd_set_amortization."""

    def test_zero_months_exits(self, services, output):
        args = Namespace(transaction_id="x" * 64, months=0)
        with pytest.raises(SystemExit) as exc:
            cmd_set_amortization(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_negative_months_exits(self, services, output):
        args = Namespace(transaction_id="x" * 64, months=-1)
        with pytest.raises(SystemExit) as exc:
            cmd_set_amortization(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_unknown_transaction_exits(self, services, output):
        args = Namespace(transaction_id="x" * 64, months=12)
        with pytest.raises(SystemExit) as exc:
            cmd_set_amortization(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_sets_amortization_correctly(self, services, output):
        account = services.accounts.create("acct", "bofa", "Test")
        txn = _make_transaction(services, account, "Annual Sub", amount=12000)
        args = Namespace(transaction_id=txn.id, months=12)
        cmd_set_amortization(args, services.db_manager, services.config, output)

        updated = services.transactions.find(txn.id)
        assert updated.amortize_months == 12
        assert updated.amortize_end_date is not None
        # Jan 15 + 12 months amortized = end of Dec (month-boundary convention)
        assert updated.amortize_end_date == date(2024, 12, 31)

    def test_single_month_amortization(self, services, output):
        account = services.accounts.create("acct", "bofa", "Test")
        txn = _make_transaction(services, account, "One-time", amount=1000)
        args = Namespace(transaction_id=txn.id, months=1)
        cmd_set_amortization(args, services.db_manager, services.config, output)

        updated = services.transactions.find(txn.id)
        assert updated.amortize_months == 1
        # months=1 → relativedelta(months=0, day=31) → Jan 31
        assert updated.amortize_end_date == date(2024, 1, 31)
