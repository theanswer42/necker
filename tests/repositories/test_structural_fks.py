"""Tests for NO ACTION FK constraints on structural references.

Covers:
- data_imports.account_id → accounts(id)
- transactions.data_import_id → data_imports(id)
"""

import sqlite3
from datetime import date

import pytest

from models.transaction import Transaction


def _make_transaction(account_id, data_import_id, raw_suffix="1"):
    t = Transaction.create_with_checksum(
        raw_data=f"row_{raw_suffix}",
        account_id=account_id,
        transaction_date=date(2025, 1, 15),
        post_date=None,
        description="Test",
        bank_category=None,
        amount=100,
        transaction_type="expense",
    )
    t.data_import_id = data_import_id
    return t


class TestStructuralForeignKeys:
    """Verify NO ACTION (block) semantics on structural FK columns."""

    def test_delete_account_with_data_imports_raises(self, services):
        """Deleting an account that has dependent data_imports must fail."""
        account = services.accounts.create("a", "bofa", "A")
        services.data_imports.create(account.id, "test.csv.gz")

        with services.db_manager.connect() as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM accounts WHERE id = ?", (account.id,))

    def test_delete_data_import_with_transactions_raises(self, services):
        """Deleting a data_import that has dependent transactions must fail."""
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, "test.csv.gz")
        t = _make_transaction(account.id, di.id)
        services.transactions.create(t)

        with services.db_manager.connect() as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM data_imports WHERE id = ?", (di.id,))

    def test_delete_account_with_no_data_imports_succeeds(self, services):
        """Deleting an account with zero data_imports succeeds."""
        account = services.accounts.create("a", "bofa", "A")

        with services.db_manager.connect() as conn:
            conn.execute("DELETE FROM accounts WHERE id = ?", (account.id,))
            row = conn.execute(
                "SELECT id FROM accounts WHERE id = ?", (account.id,)
            ).fetchone()
        assert row is None

    def test_delete_data_import_with_no_transactions_succeeds(self, services):
        """Deleting a data_import with zero transactions succeeds."""
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, "test.csv.gz")

        with services.db_manager.connect() as conn:
            conn.execute("DELETE FROM data_imports WHERE id = ?", (di.id,))
            row = conn.execute(
                "SELECT id FROM data_imports WHERE id = ?", (di.id,)
            ).fetchone()
        assert row is None

    def test_unblock_path_transaction_then_data_import_then_account(self, services):
        """Removing dependents in order allows the parent deletes to succeed."""
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, "test.csv.gz")
        t = _make_transaction(account.id, di.id)
        services.transactions.create(t)

        with services.db_manager.connect() as conn:
            conn.execute("DELETE FROM transactions WHERE id = ?", (t.id,))
            conn.execute("DELETE FROM data_imports WHERE id = ?", (di.id,))
            conn.execute("DELETE FROM accounts WHERE id = ?", (account.id,))

            assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM data_imports").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0
