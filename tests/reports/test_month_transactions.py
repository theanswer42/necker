"""Tests for MonthTransactionsReport."""

from datetime import date

import pytest
from dateutil.relativedelta import relativedelta

from models.transaction import Transaction
from reports.month_transactions import MonthTransactionsReport


class TestMonthTransactionsReport:
    def test_single_month_cash_basis_excludes_amortized(self, services):
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category = services.categories.create("Food", "Food expenses")

        regular = Transaction.create_with_checksum(
            raw_data="01/15/2024,Coffee,-5.00,1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Coffee",
            bank_category=None,
            amount=500,
            transaction_type="expense",
        )
        regular.data_import_id = data_import.id
        regular.category_id = category.id
        services.transactions.create(regular)

        amortized = Transaction.create_with_checksum(
            raw_data="01/20/2024,Subscription,-120.00,995.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 20),
            post_date=None,
            description="Annual Subscription",
            bank_category=None,
            amount=12000,
            transaction_type="expense",
        )
        amortized.data_import_id = data_import.id
        amortized.category_id = category.id
        amortized.amortize_months = 12
        amortized.amortize_end_date = amortized.transaction_date + relativedelta(
            months=11, day=31
        )
        services.transactions.create(amortized)

        result = MonthTransactionsReport(services.db_manager).run(2024, 1, "cash")

        assert result.year == 2024
        assert result.month == 1
        assert result.basis == "cash"
        assert len(result.transactions) == 1
        assert result.transactions[0].description == "Coffee"

    def test_single_month_accrual_basis(self, services):
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category = services.categories.create("Food", "Food expenses")

        amortized = Transaction.create_with_checksum(
            raw_data="01/20/2024,Subscription,-120.00,995.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 20),
            post_date=None,
            description="Annual Subscription",
            bank_category=None,
            amount=12000,
            transaction_type="expense",
        )
        amortized.data_import_id = data_import.id
        amortized.category_id = category.id
        amortized.amortize_months = 12
        amortized.amortize_end_date = amortized.transaction_date + relativedelta(
            months=11, day=31
        )
        services.transactions.create(amortized)

        result = MonthTransactionsReport(services.db_manager).run(2024, 1, "accrual")

        assert result.basis == "accrual"
        assert len(result.transactions) == 1
        assert result.transactions[0].description == "Annual Subscription"
        assert result.transactions[0].amount == 1000
        assert result.transactions[0].accrued is True

    def test_multi_month_via_caller_loop(self, services):
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        for month in [1, 2, 3]:
            t = Transaction.create_with_checksum(
                raw_data=f"0{month}/15/2024,TX{month},-10.00,1000.00",
                account_id=account.id,
                transaction_date=date(2024, month, 15),
                post_date=None,
                description=f"Transaction {month}",
                bank_category=None,
                amount=1000,
                transaction_type="expense",
            )
            t.data_import_id = data_import.id
            services.transactions.create(t)

        report = MonthTransactionsReport(services.db_manager)
        results = [report.run(2024, m, "cash") for m in [1, 2, 3]]

        assert [r.month for r in results] == [1, 2, 3]
        for r in results:
            assert r.year == 2024
            assert r.basis == "cash"
            assert len(r.transactions) == 1

    def test_cross_year_via_caller_loop(self, services):
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        dates = [date(2024, 11, 15), date(2024, 12, 15), date(2025, 1, 15)]
        for txn_date in dates:
            t = Transaction.create_with_checksum(
                raw_data=f"{txn_date.isoformat()},TX,-10.00,1000.00",
                account_id=account.id,
                transaction_date=txn_date,
                post_date=None,
                description=f"Transaction {txn_date.month}",
                bank_category=None,
                amount=1000,
                transaction_type="expense",
            )
            t.data_import_id = data_import.id
            services.transactions.create(t)

        report = MonthTransactionsReport(services.db_manager)
        nov = report.run(2024, 11, "cash")
        dec = report.run(2024, 12, "cash")
        jan = report.run(2025, 1, "cash")
        assert len(nov.transactions) == 1
        assert len(dec.transactions) == 1
        assert len(jan.transactions) == 1

    def test_category_filter(self, services):
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category1 = services.categories.create("Food", "Food expenses")
        category2 = services.categories.create("Transport", "Transport")

        t1 = Transaction.create_with_checksum(
            raw_data="01/15/2024,Coffee,-5.00,1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Coffee",
            bank_category=None,
            amount=500,
            transaction_type="expense",
        )
        t1.data_import_id = data_import.id
        t1.category_id = category1.id
        services.transactions.create(t1)

        t2 = Transaction.create_with_checksum(
            raw_data="01/20/2024,Bus,-2.00,998.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 20),
            post_date=None,
            description="Bus",
            bank_category=None,
            amount=200,
            transaction_type="expense",
        )
        t2.data_import_id = data_import.id
        t2.category_id = category2.id
        services.transactions.create(t2)

        t3 = Transaction.create_with_checksum(
            raw_data="01/25/2024,Subscription,-120.00,996.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 25),
            post_date=None,
            description="Food Subscription",
            bank_category=None,
            amount=12000,
            transaction_type="expense",
        )
        t3.data_import_id = data_import.id
        t3.category_id = category1.id
        t3.amortize_months = 12
        t3.amortize_end_date = t3.transaction_date + relativedelta(months=11, day=31)
        services.transactions.create(t3)

        report = MonthTransactionsReport(services.db_manager)
        cash = report.run(2024, 1, "cash", category_ids=[category1.id])
        assert len(cash.transactions) == 1
        assert cash.transactions[0].description == "Coffee"

        accrual = report.run(2024, 1, "accrual", category_ids=[category1.id])
        assert len(accrual.transactions) == 1
        assert accrual.transactions[0].description == "Food Subscription"

    def test_empty_month(self, services):
        services.accounts.create("test_account", "bofa", "Test Account")

        report = MonthTransactionsReport(services.db_manager)
        cash = report.run(2024, 2, "cash")
        accrual = report.run(2024, 2, "accrual")

        assert cash.year == 2024
        assert cash.month == 2
        assert cash.basis == "cash"
        assert cash.transactions == []
        assert accrual.transactions == []

    def test_accrued_spans_multiple_months(self, services):
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        t = Transaction.create_with_checksum(
            raw_data="01/15/2024,Quarterly,-300.00,1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Quarterly Subscription",
            bank_category=None,
            amount=30000,
            transaction_type="expense",
        )
        t.data_import_id = data_import.id
        t.amortize_months = 3
        t.amortize_end_date = t.transaction_date + relativedelta(months=2, day=31)
        services.transactions.create(t)

        report = MonthTransactionsReport(services.db_manager)
        for m in [1, 2, 3]:
            r = report.run(2024, m, "accrual")
            assert len(r.transactions) == 1
            assert r.transactions[0].amount == 10000

        apr = report.run(2024, 4, "accrual")
        assert apr.transactions == []

    def test_invalid_basis_raises(self, services):
        with pytest.raises(ValueError):
            MonthTransactionsReport(services.db_manager).run(2024, 1, "weekly")

    def test_output_is_self_contained(self, services):
        services.accounts.create("test_account", "bofa", "Test Account")

        result = MonthTransactionsReport(services.db_manager).run(2024, 7, "cash")
        assert result.year == 2024
        assert result.month == 7
        assert result.basis == "cash"
