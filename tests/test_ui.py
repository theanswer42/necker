"""Tests for the UI blueprint routes."""

from datetime import date

import pytest

from app.app import create_app
from models.transaction import Transaction
from services.base import Services


@pytest.fixture
def app(test_config, db_manager_with_schema):
    svc = Services(test_config, db_manager=db_manager_with_schema)
    flask_app = create_app(config=test_config, services=svc)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def svc(app):
    return app.services


@pytest.fixture
def account(svc):
    return svc.accounts.create("bofa_checking", "bofa", "Bank of America Checking")


@pytest.fixture
def category(svc):
    return svc.categories.create("Food", "Food expenses")


@pytest.fixture
def data_import(svc, account):
    return svc.data_imports.create(account_id=account.id, filename=None)


@pytest.fixture
def transaction(svc, account, data_import):
    t = Transaction.create_with_checksum(
        raw_data="ui-row1",
        account_id=account.id,
        transaction_date=date(2025, 3, 15),
        post_date=None,
        description="Grocery Store",
        bank_category="Groceries",
        amount=4200,
        transaction_type="expense",
    )
    t.data_import_id = data_import.id
    return svc.transactions.create(t)


# --- /ui/accounts ---


class TestAccountsUI:
    def test_accounts_returns_200(self, client):
        resp = client.get("/ui/accounts")
        assert resp.status_code == 200

    def test_accounts_empty(self, client):
        html = client.get("/ui/accounts").data.decode()
        assert "No accounts found" in html

    def test_accounts_lists_accounts(self, client, account):
        html = client.get("/ui/accounts").data.decode()
        assert "bofa_checking" in html
        assert "Bank of America Checking" in html

    def test_accounts_renders_table(self, client, account):
        html = client.get("/ui/accounts").data.decode()
        assert "<table>" in html
        assert "<th>" in html


# --- /ui/categories ---


class TestCategoriesUI:
    def test_categories_returns_200(self, client):
        resp = client.get("/ui/categories")
        assert resp.status_code == 200

    def test_categories_empty(self, client):
        html = client.get("/ui/categories").data.decode()
        assert "No categories found" in html

    def test_categories_lists_categories(self, client, category):
        html = client.get("/ui/categories").data.decode()
        assert "Food" in html
        assert "Food expenses" in html


# --- /ui/transactions ---


class TestTransactionsUI:
    def test_transactions_returns_200_with_month(self, client):
        resp = client.get("/ui/transactions?month=2025/03")
        assert resp.status_code == 200

    def test_transactions_defaults_to_current_month(self, client):
        # No month param — should not error
        resp = client.get("/ui/transactions")
        assert resp.status_code == 200

    def test_transactions_invalid_month_returns_400(self, client):
        resp = client.get("/ui/transactions?month=2025-03")
        assert resp.status_code == 400

    def test_transactions_invalid_month_shows_error(self, client):
        html = client.get("/ui/transactions?month=badmonth").data.decode()
        assert "Error" in html

    def test_transactions_empty_month(self, client):
        html = client.get("/ui/transactions?month=2025/01").data.decode()
        assert "No transactions" in html

    def test_transactions_shows_month_label(self, client):
        html = client.get("/ui/transactions?month=2025/03").data.decode()
        assert "2025/03" in html

    def test_transactions_shows_prev_next_navigation(self, client):
        html = client.get("/ui/transactions?month=2025/03").data.decode()
        assert "2025/02" in html  # prev month
        assert "2025/04" in html  # next month

    def test_transactions_lists_transactions(self, client, transaction):
        html = client.get("/ui/transactions?month=2025/03").data.decode()
        assert "Grocery Store" in html
        assert "42.00" in html  # $42.00

    def test_transactions_renders_table(self, client, transaction):
        html = client.get("/ui/transactions?month=2025/03").data.decode()
        assert "<table>" in html

    def test_transactions_year_boundary_prev(self, client):
        # January → prev should be December of previous year
        html = client.get("/ui/transactions?month=2025/01").data.decode()
        assert "2024/12" in html

    def test_transactions_year_boundary_next(self, client):
        # December → next should be January of next year
        html = client.get("/ui/transactions?month=2025/12").data.decode()
        assert "2026/01" in html
