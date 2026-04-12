"""Tests for budget API endpoints."""

import pytest

from app.app import create_app
from repositories.budgets import BudgetRepository
from repositories.categories import CategoryRepository


@pytest.fixture
def app(test_config, db_manager_with_schema):
    flask_app = create_app(config=test_config, db_manager=db_manager_with_schema)
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def repos(app):
    db = app.db_manager

    class _Repos:
        categories = CategoryRepository(db)
        budgets = BudgetRepository(db)

    return _Repos()


@pytest.fixture
def category(repos):
    return repos.categories.create("Food", "Food expenses")


@pytest.fixture
def budget(repos, category):
    return repos.budgets.create(category.id, "monthly", 50000)


class TestListBudgets:
    def test_empty(self, client):
        resp = client.get("/api/budgets")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_with_budget(self, client, budget, category):
        resp = client.get("/api/budgets")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["id"] == budget.id
        assert data[0]["category_id"] == category.id
        assert data[0]["period_type"] == "monthly"
        assert data[0]["amount"] == 50000
        assert data[0]["category_name"] == category.name


class TestCreateBudget:
    def test_success(self, client, category):
        resp = client.post(
            "/api/budgets",
            json={
                "category_id": category.id,
                "period_type": "monthly",
                "amount": 30000,
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["category_id"] == category.id
        assert data["period_type"] == "monthly"
        assert data["amount"] == 30000

    def test_missing_category_id(self, client):
        resp = client.post(
            "/api/budgets", json={"period_type": "monthly", "amount": 30000}
        )
        assert resp.status_code == 400

    def test_invalid_period_type(self, client, category):
        resp = client.post(
            "/api/budgets",
            json={"category_id": category.id, "period_type": "weekly", "amount": 30000},
        )
        assert resp.status_code == 400

    def test_zero_amount(self, client, category):
        resp = client.post(
            "/api/budgets",
            json={"category_id": category.id, "period_type": "monthly", "amount": 0},
        )
        assert resp.status_code == 400

    def test_negative_amount(self, client, category):
        resp = client.post(
            "/api/budgets",
            json={"category_id": category.id, "period_type": "monthly", "amount": -100},
        )
        assert resp.status_code == 400

    def test_bogus_category_id(self, client):
        resp = client.post(
            "/api/budgets",
            json={"category_id": 9999, "period_type": "monthly", "amount": 30000},
        )
        assert resp.status_code == 400

    def test_duplicate_raises_400(self, client, category, budget):
        resp = client.post(
            "/api/budgets",
            json={
                "category_id": category.id,
                "period_type": "monthly",
                "amount": 99999,
            },
        )
        assert resp.status_code == 400
        assert "already exists" in resp.get_json()["message"]


class TestDeleteBudget:
    def test_success(self, client, budget):
        resp = client.delete(f"/api/budgets/{budget.id}")
        assert resp.status_code == 204

    def test_not_found(self, client):
        resp = client.delete("/api/budgets/9999")
        assert resp.status_code == 404


class TestPatchBudget:
    def test_success(self, client, budget):
        resp = client.patch(f"/api/budgets/{budget.id}", json={"amount": 75000})
        assert resp.status_code == 200
        assert resp.get_json()["amount"] == 75000

    def test_not_found(self, client):
        resp = client.patch("/api/budgets/9999", json={"amount": 75000})
        assert resp.status_code == 404

    def test_zero_amount(self, client, budget):
        resp = client.patch(f"/api/budgets/{budget.id}", json={"amount": 0})
        assert resp.status_code == 400

    def test_missing_amount(self, client, budget):
        resp = client.patch(f"/api/budgets/{budget.id}", json={})
        assert resp.status_code == 400
