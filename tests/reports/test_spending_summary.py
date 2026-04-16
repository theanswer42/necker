"""Tests for CashSpendingSummaryReport and AccrualSpendingSummaryReport."""

from datetime import date

from dateutil.relativedelta import relativedelta

from models.transaction import Transaction
from reports.accrual_spending_summary import AccrualSpendingSummaryReport
from reports.cash_spending_summary import CashSpendingSummaryReport


class TestCashSpendingSummaryReport:
    def test_basic_summary(self, services):
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category1 = services.categories.create("Food", "Food expenses")
        category2 = services.categories.create("Transport", "Transportation")

        t1 = Transaction.create_with_checksum(
            raw_data="01/05/2024,Salary,2000.00,2000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 5),
            post_date=None,
            description="Salary",
            bank_category=None,
            amount=200000,
            transaction_type="income",
        )
        t1.data_import_id = data_import.id
        services.transactions.create(t1)

        t2 = Transaction.create_with_checksum(
            raw_data="01/15/2024,Groceries,-150.00,1850.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Groceries",
            bank_category=None,
            amount=15000,
            transaction_type="expense",
        )
        t2.data_import_id = data_import.id
        t2.category_id = category1.id
        services.transactions.create(t2)

        t3 = Transaction.create_with_checksum(
            raw_data="01/20/2024,Gas,-50.00,1800.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 20),
            post_date=None,
            description="Gas",
            bank_category=None,
            amount=5000,
            transaction_type="expense",
        )
        t3.data_import_id = data_import.id
        t3.category_id = category2.id
        services.transactions.create(t3)

        summary = CashSpendingSummaryReport(services.db_manager).run(2024, 1)

        assert summary.year == 2024
        assert summary.month == 1
        assert summary.basis == "cash"
        assert summary.income_total == 200000
        assert summary.expense_total == 20000
        assert summary.net == 180000
        assert summary.expenses_by_category[category1.id] == 15000
        assert summary.expenses_by_category[category2.id] == 5000

    def test_uncategorized_expenses(self, services):
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        t = Transaction.create_with_checksum(
            raw_data="01/15/2024,Mystery,-100.00,900.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Mystery expense",
            bank_category=None,
            amount=10000,
            transaction_type="expense",
        )
        t.data_import_id = data_import.id
        services.transactions.create(t)

        summary = CashSpendingSummaryReport(services.db_manager).run(2024, 1)
        assert summary.expense_total == 10000
        assert summary.expenses_by_category[0] == 10000

    def test_multiple_expenses_same_category(self, services):
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category = services.categories.create("Food", "Food expenses")

        for i in range(3):
            t = Transaction.create_with_checksum(
                raw_data=f"01/{10 + i}/2024,Food{i},-50.00,{950 - i * 50}.00",
                account_id=account.id,
                transaction_date=date(2024, 1, 10 + i),
                post_date=None,
                description=f"Food {i}",
                bank_category=None,
                amount=5000,
                transaction_type="expense",
            )
            t.data_import_id = data_import.id
            t.category_id = category.id
            services.transactions.create(t)

        summary = CashSpendingSummaryReport(services.db_manager).run(2024, 1)
        assert summary.expense_total == 15000
        assert summary.expenses_by_category[category.id] == 15000

    def test_empty_month(self, services):
        services.accounts.create("test_account", "bofa", "Test Account")

        summary = CashSpendingSummaryReport(services.db_manager).run(2024, 2)
        assert summary.year == 2024
        assert summary.month == 2
        assert summary.basis == "cash"
        assert summary.income_total == 0
        assert summary.expense_total == 0
        assert summary.net == 0
        assert summary.expenses_by_category == {}

    def test_category_filter(self, services):
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category1 = services.categories.create("Food", "Food expenses")
        category2 = services.categories.create("Transport", "Transportation")

        t1 = Transaction.create_with_checksum(
            raw_data="01/15/2024,Food,-100.00,900.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Food",
            bank_category=None,
            amount=10000,
            transaction_type="expense",
        )
        t1.data_import_id = data_import.id
        t1.category_id = category1.id
        services.transactions.create(t1)

        t2 = Transaction.create_with_checksum(
            raw_data="01/20/2024,Gas,-50.00,850.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 20),
            post_date=None,
            description="Gas",
            bank_category=None,
            amount=5000,
            transaction_type="expense",
        )
        t2.data_import_id = data_import.id
        t2.category_id = category2.id
        services.transactions.create(t2)

        summary = CashSpendingSummaryReport(services.db_manager).run(
            2024, 1, category_ids=[category1.id]
        )
        assert summary.expense_total == 10000
        assert summary.expenses_by_category[category1.id] == 10000
        assert category2.id not in summary.expenses_by_category

    def test_multi_month_via_caller_loop(self, services):
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category = services.categories.create("Food", "Food expenses")

        for month in [1, 2, 3]:
            t = Transaction.create_with_checksum(
                raw_data=f"0{month}/15/2024,Food{month},-{month * 100}.00,1000.00",
                account_id=account.id,
                transaction_date=date(2024, month, 15),
                post_date=None,
                description=f"Food {month}",
                bank_category=None,
                amount=month * 10000,
                transaction_type="expense",
            )
            t.data_import_id = data_import.id
            t.category_id = category.id
            services.transactions.create(t)

        report = CashSpendingSummaryReport(services.db_manager)
        jan = report.run(2024, 1)
        feb = report.run(2024, 2)
        mar = report.run(2024, 3)

        assert jan.expense_total == 10000
        assert feb.expense_total == 20000
        assert mar.expense_total == 30000


class TestAccrualSpendingSummaryReport:
    def test_accrual_basis_summary(self, services):
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category = services.categories.create("Subscriptions", "Subscription services")

        t = Transaction.create_with_checksum(
            raw_data="01/15/2024,Annual,-120.00,1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Annual Subscription",
            bank_category=None,
            amount=12000,
            transaction_type="expense",
        )
        t.data_import_id = data_import.id
        t.category_id = category.id
        t.amortize_months = 12
        t.amortize_end_date = t.transaction_date + relativedelta(months=11, day=31)
        services.transactions.create(t)

        cash = CashSpendingSummaryReport(services.db_manager).run(2024, 1)
        assert cash.expense_total == 0
        assert cash.expenses_by_category == {}

        accrual = AccrualSpendingSummaryReport(services.db_manager).run(2024, 1)
        assert accrual.basis == "accrual"
        assert accrual.expense_total == 1000
        assert accrual.expenses_by_category[category.id] == 1000

    def test_empty_month(self, services):
        services.accounts.create("test_account", "bofa", "Test Account")

        summary = AccrualSpendingSummaryReport(services.db_manager).run(2024, 2)
        assert summary.basis == "accrual"
        assert summary.income_total == 0
        assert summary.expense_total == 0
        assert summary.net == 0
        assert summary.expenses_by_category == {}
