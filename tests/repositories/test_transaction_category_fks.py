"""Tests for foreign key constraints on transactions.category_id and auto_category_id."""

import sqlite3
from datetime import date

import pytest

from models.transaction import Transaction


def _make_transaction(account_id, data_import_id, raw_suffix="1", **overrides):
    """Helper to build a Transaction with valid defaults."""
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
    for k, v in overrides.items():
        setattr(t, k, v)
    return t


class TestCategoryForeignKeys:
    """Verify FK constraints on category_id and auto_category_id."""

    def test_bogus_category_id_raises_integrity_error(self, services):
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, "test.csv.gz")
        t = _make_transaction(account.id, di.id, category_id=99999)

        with pytest.raises(sqlite3.IntegrityError):
            services.transactions.create(t)

    def test_bogus_auto_category_id_raises_integrity_error(self, services):
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, "test.csv.gz")
        t = _make_transaction(account.id, di.id, raw_suffix="2", auto_category_id=99999)

        with pytest.raises(sqlite3.IntegrityError):
            services.transactions.create(t)

    def test_null_category_id_allowed(self, services):
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, "test.csv.gz")
        t = _make_transaction(account.id, di.id)
        assert t.category_id is None

        created = services.transactions.create(t)
        assert created.category_id is None

    def test_valid_category_id_accepted(self, services):
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, "test.csv.gz")
        cat = services.categories.create("Food")
        t = _make_transaction(account.id, di.id, category_id=cat.id)

        created = services.transactions.create(t)
        assert created.category_id == cat.id

    def test_delete_category_nulls_category_id(self, services):
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, "test.csv.gz")
        cat = services.categories.create("Food")
        t = _make_transaction(account.id, di.id, category_id=cat.id)
        services.transactions.create(t)

        services.categories.delete(cat.id)

        found = services.transactions.find(t.id)
        assert found is not None
        assert found.category_id is None

    def test_delete_category_nulls_auto_category_id(self, services):
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, "test.csv.gz")
        cat = services.categories.create("Food")
        t = _make_transaction(
            account.id, di.id, raw_suffix="3", auto_category_id=cat.id
        )
        services.transactions.create(t)

        services.categories.delete(cat.id)

        found = services.transactions.find(t.id)
        assert found is not None
        assert found.auto_category_id is None
