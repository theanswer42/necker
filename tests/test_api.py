"""Tests for the API blueprint routes."""

import pytest
from datetime import date

from app.app import create_app
from models.transaction import Transaction
from repositories.accounts import AccountRepository
from repositories.budgets import BudgetRepository
from repositories.categories import CategoryRepository
from repositories.data_imports import DataImportRepository
from repositories.transactions import TransactionRepository


@pytest.fixture
def app(test_config, db_manager_with_schema):
    flask_app = create_app(config=test_config, db_manager=db_manager_with_schema)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def repos(app):
    """Convenience access to repositories."""
    db = app.db_manager

    class _Repos:
        accounts = AccountRepository(db)
        transactions = TransactionRepository(db)
        categories = CategoryRepository(db)
        data_imports = DataImportRepository(db)
        budgets = BudgetRepository(db)

    return _Repos()


@pytest.fixture
def account(repos):
    return repos.accounts.create("bofa_checking", "bofa", "Bank of America Checking")


@pytest.fixture
def category(repos):
    return repos.categories.create("Food", "Food expenses")


@pytest.fixture
def data_import(repos, account):
    return repos.data_imports.create(account_id=account.id, filename=None)


@pytest.fixture
def transaction(repos, account, data_import):
    t = Transaction.create_with_checksum(
        raw_data="row1",
        account_id=account.id,
        transaction_date=date(2025, 3, 15),
        post_date=None,
        description="Grocery Store",
        bank_category="Groceries",
        amount=4200,
        transaction_type="expense",
    )
    t.data_import_id = data_import.id
    return repos.transactions.create(t)


# --- Accounts ---


class TestAccountsAPI:
    def test_list_accounts_empty(self, client):
        resp = client.get("/api/accounts")
        assert resp.status_code == 200
        assert resp.json == []

    def test_list_accounts_returns_accounts(self, client, account):
        resp = client.get("/api/accounts")
        assert resp.status_code == 200
        data = resp.json
        assert len(data) == 1
        assert data[0]["name"] == "bofa_checking"
        assert data[0]["id"] == account.id

    def test_get_account_found(self, client, account):
        resp = client.get(f"/api/accounts/{account.id}")
        assert resp.status_code == 200
        assert resp.json["name"] == "bofa_checking"

    def test_get_account_not_found(self, client):
        resp = client.get("/api/accounts/9999")
        assert resp.status_code == 404
        assert resp.json["error"] == "not_found"


# --- Categories ---


class TestCategoriesAPI:
    def test_list_categories_empty(self, client):
        resp = client.get("/api/categories")
        assert resp.status_code == 200
        assert resp.json == []

    def test_list_categories_returns_categories(self, client, category):
        resp = client.get("/api/categories")
        assert resp.status_code == 200
        data = resp.json
        assert len(data) == 1
        assert data[0]["name"] == "Food"


# --- Transactions ---


class TestTransactionsAPI:
    def test_list_transactions_missing_month(self, client):
        resp = client.get("/api/transactions")
        assert resp.status_code == 400
        assert resp.json["error"] == "bad_request"

    def test_list_transactions_bad_month_format(self, client):
        resp = client.get("/api/transactions?month=2025-03")
        assert resp.status_code == 400
        assert resp.json["error"] == "bad_request"

    def test_list_transactions_empty_month(self, client, account):
        resp = client.get("/api/transactions?month=2025/01")
        assert resp.status_code == 200
        assert resp.json == []

    def test_list_transactions_returns_transactions(self, client, transaction):
        resp = client.get("/api/transactions?month=2025/03")
        assert resp.status_code == 200
        data = resp.json
        assert len(data) == 1
        assert data[0]["description"] == "Grocery Store"
        assert data[0]["amount"] == 4200
        assert data[0]["transaction_date"] == "2025-03-15"

    def test_get_transaction_found(self, client, transaction):
        resp = client.get(f"/api/transactions/{transaction.id}")
        assert resp.status_code == 200
        assert resp.json["description"] == "Grocery Store"

    def test_get_transaction_not_found(self, client):
        resp = client.get("/api/transactions/nonexistent-id")
        assert resp.status_code == 404
        assert resp.json["error"] == "not_found"


# --- Summary ---


class TestSummaryAPI:
    def test_summary_missing_start(self, client):
        resp = client.get("/api/transactions/summary?end=2025/03")
        assert resp.status_code == 400
        assert resp.json["error"] == "bad_request"

    def test_summary_missing_end(self, client):
        resp = client.get("/api/transactions/summary?start=2025/01")
        assert resp.status_code == 400
        assert resp.json["error"] == "bad_request"

    def test_summary_bad_format(self, client):
        resp = client.get("/api/transactions/summary?start=2025-01&end=2025-03")
        assert resp.status_code == 400
        assert resp.json["error"] == "bad_request"

    def test_summary_end_before_start(self, client):
        resp = client.get("/api/transactions/summary?start=2025/03&end=2025/01")
        assert resp.status_code == 400
        assert resp.json["error"] == "bad_request"

    def test_summary_empty_period(self, client, account):
        resp = client.get("/api/transactions/summary?start=2025/01&end=2025/01")
        assert resp.status_code == 200
        data = resp.json
        assert "cash_basis" in data
        assert "accrual_basis" in data
        assert "2025/01" in data["cash_basis"]
        assert data["cash_basis"]["2025/01"]["income_total"] == 0
        assert data["cash_basis"]["2025/01"]["expense_total"] == 0

    def test_summary_with_transactions(self, client, transaction):
        resp = client.get("/api/transactions/summary?start=2025/03&end=2025/03")
        assert resp.status_code == 200
        data = resp.json
        month = data["cash_basis"]["2025/03"]
        assert month["expense_total"] == 4200
        assert month["income_total"] == 0
        assert month["net"] == -4200
