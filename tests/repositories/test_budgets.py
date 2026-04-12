"""Tests for BudgetRepository — CRUD, FK enforcement, uniqueness, check constraint."""

import sqlite3

import pytest


@pytest.fixture
def category(services):
    return services.categories.create("Food", "Food expenses")


@pytest.fixture
def category2(services):
    return services.categories.create("Transport", "Transport expenses")


class TestBudgetCRUD:
    def test_create_and_find(self, services, category):
        budget = services.budgets.create(category.id, "monthly", 50000)
        assert budget.id is not None
        assert budget.category_id == category.id
        assert budget.period_type == "monthly"
        assert budget.amount == 50000
        assert budget.category_name == category.name

    def test_find_not_found(self, services):
        assert services.budgets.find(9999) is None

    def test_find_all_empty(self, services):
        assert services.budgets.find_all() == []

    def test_find_all_ordered_by_category_name(self, services, category, category2):
        services.budgets.create(category2.id, "monthly", 10000)
        services.budgets.create(category.id, "monthly", 20000)
        budgets = services.budgets.find_all()
        names = [b.category_name for b in budgets]
        assert names == sorted(names)

    def test_update_amount(self, services, category):
        budget = services.budgets.create(category.id, "monthly", 50000)
        updated = services.budgets.update_amount(budget.id, 75000)
        assert updated.amount == 75000
        assert updated.id == budget.id

    def test_update_amount_not_found(self, services):
        result = services.budgets.update_amount(9999, 50000)
        assert result is None

    def test_delete(self, services, category):
        budget = services.budgets.create(category.id, "monthly", 50000)
        assert services.budgets.delete(budget.id) is True
        assert services.budgets.find(budget.id) is None

    def test_delete_not_found(self, services):
        assert services.budgets.delete(9999) is False

    def test_both_period_types(self, services, category):
        monthly = services.budgets.create(category.id, "monthly", 10000)
        yearly = services.budgets.create(category.id, "yearly", 100000)
        assert monthly.period_type == "monthly"
        assert yearly.period_type == "yearly"
        assert len(services.budgets.find_all()) == 2


class TestBudgetConstraints:
    def test_uniqueness_constraint(self, services, category):
        services.budgets.create(category.id, "monthly", 50000)
        with pytest.raises(sqlite3.IntegrityError):
            services.budgets.create(category.id, "monthly", 60000)

    def test_fk_bogus_category_raises(self, services):
        with pytest.raises(sqlite3.IntegrityError):
            services.budgets.create(9999, "monthly", 50000)

    def test_no_action_delete_category_with_budget_raises(self, services, category):
        services.budgets.create(category.id, "monthly", 50000)
        with services.db_manager.connect() as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM categories WHERE id = ?", (category.id,))

    def test_check_constraint_invalid_period_type(self, services, category):
        with services.db_manager.connect() as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO budgets (category_id, period_type, amount) VALUES (?, ?, ?)",
                    (category.id, "weekly", 50000),
                )
