"""Tests for transaction analysis tools."""

from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from models.transaction import Transaction
from tools.transactions import get_period_transactions, get_period_summary


class TestGetPeriodTransactions:
    """Tests for get_period_transactions function."""

    def test_single_month_period(self, services):
        """Test getting transactions for a single month."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category = services.categories.create("Food", "Food expenses")

        # Create regular transaction
        t1 = Transaction.create_with_checksum(
            raw_data="01/15/2024,Coffee,-5.00,1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Coffee",
            bank_category=None,
            amount=Decimal("5.00"),
            type="expense",
        )
        t1.data_import_id = data_import.id
        t1.category_id = category.id
        services.transactions.create(t1)

        # Create amortized transaction
        t2 = Transaction.create_with_checksum(
            raw_data="01/20/2024,Subscription,-120.00,995.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 20),
            post_date=None,
            description="Annual Subscription",
            bank_category=None,
            amount=Decimal("120.00"),
            type="expense",
        )
        t2.data_import_id = data_import.id
        t2.category_id = category.id
        t2.amortize_months = 12
        t2.amortize_end_date = t2.transaction_date + relativedelta(months=11, day=31)
        services.transactions.create(t2)

        # Get period transactions for January 2024
        result = get_period_transactions(
            services,
            date(2024, 1, 1),
            date(2024, 1, 31),
        )

        assert "cash_basis" in result
        assert "accrual_basis" in result
        assert "2024/01" in result["cash_basis"]
        assert len(result["cash_basis"]) == 1

        # Cash basis should have only the regular transaction
        cash_basis = result["cash_basis"]["2024/01"]
        assert len(cash_basis) == 1
        assert cash_basis[0].description == "Coffee"

        # Accrual basis should have the amortized transaction
        accrual_basis = result["accrual_basis"]["2024/01"]
        assert len(accrual_basis) == 1
        assert accrual_basis[0].description == "Annual Subscription"
        assert accrual_basis[0].amount == Decimal("10.00")
        assert accrual_basis[0].accrued is True

    def test_multi_month_period(self, services):
        """Test getting transactions for multiple months."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Create transactions in different months
        for month in [1, 2, 3]:
            t = Transaction.create_with_checksum(
                raw_data=f"0{month}/15/2024,TX{month},-10.00,1000.00",
                account_id=account.id,
                transaction_date=date(2024, month, 15),
                post_date=None,
                description=f"Transaction {month}",
                bank_category=None,
                amount=Decimal("10.00"),
                type="expense",
            )
            t.data_import_id = data_import.id
            services.transactions.create(t)

        # Get Q1 2024
        result = get_period_transactions(
            services,
            date(2024, 1, 1),
            date(2024, 3, 31),
        )

        assert len(result["cash_basis"]) == 3
        assert "2024/01" in result["cash_basis"]
        assert "2024/02" in result["cash_basis"]
        assert "2024/03" in result["cash_basis"]

        # Each month should have one cash basis transaction
        for month_key in ["2024/01", "2024/02", "2024/03"]:
            assert len(result["cash_basis"][month_key]) == 1
            assert len(result["accrual_basis"][month_key]) == 0

    def test_cross_year_period(self, services):
        """Test period that crosses year boundaries."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Create transactions in Nov 2024, Dec 2024, Jan 2025
        dates = [date(2024, 11, 15), date(2024, 12, 15), date(2025, 1, 15)]
        for txn_date in dates:
            t = Transaction.create_with_checksum(
                raw_data=f"{txn_date.isoformat()},TX,-10.00,1000.00",
                account_id=account.id,
                transaction_date=txn_date,
                post_date=None,
                description=f"Transaction {txn_date.month}",
                bank_category=None,
                amount=Decimal("10.00"),
                type="expense",
            )
            t.data_import_id = data_import.id
            services.transactions.create(t)

        # Get Nov 2024 - Jan 2025
        result = get_period_transactions(
            services,
            date(2024, 11, 1),
            date(2025, 1, 31),
        )

        assert len(result["cash_basis"]) == 3
        assert "2024/11" in result["cash_basis"]
        assert "2024/12" in result["cash_basis"]
        assert "2025/01" in result["cash_basis"]

    def test_category_filter(self, services):
        """Test filtering by category IDs."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category1 = services.categories.create("Food", "Food expenses")
        category2 = services.categories.create("Transport", "Transport")

        # Create transaction with category1
        t1 = Transaction.create_with_checksum(
            raw_data="01/15/2024,Coffee,-5.00,1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Coffee",
            bank_category=None,
            amount=Decimal("5.00"),
            type="expense",
        )
        t1.data_import_id = data_import.id
        t1.category_id = category1.id
        services.transactions.create(t1)

        # Create transaction with category2
        t2 = Transaction.create_with_checksum(
            raw_data="01/20/2024,Bus,-2.00,998.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 20),
            post_date=None,
            description="Bus",
            bank_category=None,
            amount=Decimal("2.00"),
            type="expense",
        )
        t2.data_import_id = data_import.id
        t2.category_id = category2.id
        services.transactions.create(t2)

        # Create amortized transaction with category1
        t3 = Transaction.create_with_checksum(
            raw_data="01/25/2024,Subscription,-120.00,996.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 25),
            post_date=None,
            description="Food Subscription",
            bank_category=None,
            amount=Decimal("120.00"),
            type="expense",
        )
        t3.data_import_id = data_import.id
        t3.category_id = category1.id
        t3.amortize_months = 12
        t3.amortize_end_date = t3.transaction_date + relativedelta(months=11, day=31)
        services.transactions.create(t3)

        # Filter by category1 only
        result = get_period_transactions(
            services,
            date(2024, 1, 1),
            date(2024, 1, 31),
            category_ids=[category1.id],
        )

        # Should only get Food category transactions
        cash_basis = result["cash_basis"]["2024/01"]
        assert len(cash_basis) == 1
        assert cash_basis[0].description == "Coffee"

        accrual_basis = result["accrual_basis"]["2024/01"]
        assert len(accrual_basis) == 1
        assert accrual_basis[0].description == "Food Subscription"

    def test_empty_months_included(self, services):
        """Test that empty months are included in the result."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Create transaction only in January
        t = Transaction.create_with_checksum(
            raw_data="01/15/2024,Coffee,-5.00,1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Coffee",
            bank_category=None,
            amount=Decimal("5.00"),
            type="expense",
        )
        t.data_import_id = data_import.id
        services.transactions.create(t)

        # Get Jan-Mar 2024 (Feb and Mar will be empty)
        result = get_period_transactions(
            services,
            date(2024, 1, 1),
            date(2024, 3, 31),
        )

        assert len(result["cash_basis"]) == 3
        assert "2024/01" in result["cash_basis"]
        assert "2024/02" in result["cash_basis"]
        assert "2024/03" in result["cash_basis"]

        # January has transactions
        assert len(result["cash_basis"]["2024/01"]) == 1

        # February and March are empty
        assert len(result["cash_basis"]["2024/02"]) == 0
        assert len(result["accrual_basis"]["2024/02"]) == 0
        assert len(result["cash_basis"]["2024/03"]) == 0
        assert len(result["accrual_basis"]["2024/03"]) == 0

    def test_accrued_transaction_spans_multiple_months(self, services):
        """Test that amortized transactions appear in multiple months."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Create 3-month amortized transaction starting in January
        t = Transaction.create_with_checksum(
            raw_data="01/15/2024,Quarterly,-300.00,1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Quarterly Subscription",
            bank_category=None,
            amount=Decimal("300.00"),
            type="expense",
        )
        t.data_import_id = data_import.id
        t.amortize_months = 3
        t.amortize_end_date = t.transaction_date + relativedelta(months=2, day=31)
        services.transactions.create(t)

        # Get Jan-Apr 2024
        result = get_period_transactions(
            services,
            date(2024, 1, 1),
            date(2024, 4, 30),
        )

        # Accrual should appear in Jan, Feb, Mar but not Apr
        assert len(result["accrual_basis"]["2024/01"]) == 1
        assert result["accrual_basis"]["2024/01"][0].amount == Decimal("100.00")

        assert len(result["accrual_basis"]["2024/02"]) == 1
        assert result["accrual_basis"]["2024/02"][0].amount == Decimal("100.00")

        assert len(result["accrual_basis"]["2024/03"]) == 1
        assert result["accrual_basis"]["2024/03"][0].amount == Decimal("100.00")

        assert len(result["accrual_basis"]["2024/04"]) == 0


class TestGetPeriodSummary:
    """Tests for get_period_summary function."""

    def test_basic_summary(self, services):
        """Test basic summary with income and expenses."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category1 = services.categories.create("Food", "Food expenses")
        category2 = services.categories.create("Transport", "Transportation")

        # Create income transaction
        t1 = Transaction.create_with_checksum(
            raw_data="01/05/2024,Salary,2000.00,2000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 5),
            post_date=None,
            description="Salary",
            bank_category=None,
            amount=Decimal("2000.00"),
            type="income",
        )
        t1.data_import_id = data_import.id
        services.transactions.create(t1)

        # Create expense transactions
        t2 = Transaction.create_with_checksum(
            raw_data="01/15/2024,Groceries,-150.00,1850.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Groceries",
            bank_category=None,
            amount=Decimal("150.00"),
            type="expense",
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
            amount=Decimal("50.00"),
            type="expense",
        )
        t3.data_import_id = data_import.id
        t3.category_id = category2.id
        services.transactions.create(t3)

        # Get summary
        result = get_period_summary(
            services,
            date(2024, 1, 1),
            date(2024, 1, 31),
        )

        # Check cash basis summary
        summary = result["cash_basis"]["2024/01"]
        assert summary["income_total"] == Decimal("2000.00")
        assert summary["expense_total"] == Decimal("200.00")
        assert summary["net"] == Decimal("1800.00")
        assert summary["expenses_by_category"][category1.id] == Decimal("150.00")
        assert summary["expenses_by_category"][category2.id] == Decimal("50.00")

    def test_uncategorized_expenses(self, services):
        """Test that uncategorized expenses use category_id=0."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Create expense without category
        t = Transaction.create_with_checksum(
            raw_data="01/15/2024,Mystery,-100.00,900.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Mystery expense",
            bank_category=None,
            amount=Decimal("100.00"),
            type="expense",
        )
        t.data_import_id = data_import.id
        # No category_id set
        services.transactions.create(t)

        result = get_period_summary(
            services,
            date(2024, 1, 1),
            date(2024, 1, 31),
        )

        summary = result["cash_basis"]["2024/01"]
        assert summary["expense_total"] == Decimal("100.00")
        assert summary["expenses_by_category"][0] == Decimal("100.00")

    def test_multiple_expenses_same_category(self, services):
        """Test that multiple expenses in the same category are summed."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category = services.categories.create("Food", "Food expenses")

        # Create multiple food expenses
        for i in range(3):
            t = Transaction.create_with_checksum(
                raw_data=f"01/{10 + i}/2024,Food{i},-50.00,{950 - i * 50}.00",
                account_id=account.id,
                transaction_date=date(2024, 1, 10 + i),
                post_date=None,
                description=f"Food {i}",
                bank_category=None,
                amount=Decimal("50.00"),
                type="expense",
            )
            t.data_import_id = data_import.id
            t.category_id = category.id
            services.transactions.create(t)

        result = get_period_summary(
            services,
            date(2024, 1, 1),
            date(2024, 1, 31),
        )

        summary = result["cash_basis"]["2024/01"]
        assert summary["expense_total"] == Decimal("150.00")
        assert summary["expenses_by_category"][category.id] == Decimal("150.00")

    def test_accrual_basis_summary(self, services):
        """Test summary for accrual basis with amortized transactions."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category = services.categories.create("Subscriptions", "Subscription services")

        # Create amortized transaction
        t = Transaction.create_with_checksum(
            raw_data="01/15/2024,Annual,-120.00,1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Annual Subscription",
            bank_category=None,
            amount=Decimal("120.00"),
            type="expense",
        )
        t.data_import_id = data_import.id
        t.category_id = category.id
        t.amortize_months = 12
        t.amortize_end_date = t.transaction_date + relativedelta(months=11, day=31)
        services.transactions.create(t)

        result = get_period_summary(
            services,
            date(2024, 1, 1),
            date(2024, 1, 31),
        )

        # Cash basis should be empty (transaction is amortized)
        cash_summary = result["cash_basis"]["2024/01"]
        assert cash_summary["expense_total"] == Decimal("0")
        assert len(cash_summary["expenses_by_category"]) == 0

        # Accrual basis should show monthly amount
        accrual_summary = result["accrual_basis"]["2024/01"]
        assert accrual_summary["expense_total"] == Decimal("10.00")
        assert accrual_summary["expenses_by_category"][category.id] == Decimal("10.00")

    def test_empty_month_summary(self, services):
        """Test that empty months have zero values."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Create transaction only in January
        t = Transaction.create_with_checksum(
            raw_data="01/15/2024,Coffee,-5.00,1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Coffee",
            bank_category=None,
            amount=Decimal("5.00"),
            type="expense",
        )
        t.data_import_id = data_import.id
        services.transactions.create(t)

        # Get Jan-Mar summary
        result = get_period_summary(
            services,
            date(2024, 1, 1),
            date(2024, 3, 31),
        )

        # January has data
        jan_summary = result["cash_basis"]["2024/01"]
        assert jan_summary["expense_total"] == Decimal("5.00")

        # February and March are empty
        feb_summary = result["cash_basis"]["2024/02"]
        assert feb_summary["income_total"] == Decimal("0")
        assert feb_summary["expense_total"] == Decimal("0")
        assert feb_summary["net"] == Decimal("0")
        assert len(feb_summary["expenses_by_category"]) == 0

        mar_summary = result["cash_basis"]["2024/03"]
        assert mar_summary["income_total"] == Decimal("0")
        assert mar_summary["expense_total"] == Decimal("0")
        assert mar_summary["net"] == Decimal("0")
        assert len(mar_summary["expenses_by_category"]) == 0

    def test_category_filter(self, services):
        """Test filtering by category IDs."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category1 = services.categories.create("Food", "Food expenses")
        category2 = services.categories.create("Transport", "Transportation")

        # Create expenses in different categories
        t1 = Transaction.create_with_checksum(
            raw_data="01/15/2024,Food,-100.00,900.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Food",
            bank_category=None,
            amount=Decimal("100.00"),
            type="expense",
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
            amount=Decimal("50.00"),
            type="expense",
        )
        t2.data_import_id = data_import.id
        t2.category_id = category2.id
        services.transactions.create(t2)

        # Filter by category1 only
        result = get_period_summary(
            services,
            date(2024, 1, 1),
            date(2024, 1, 31),
            category_ids=[category1.id],
        )

        summary = result["cash_basis"]["2024/01"]
        # Should only include food expense
        assert summary["expense_total"] == Decimal("100.00")
        assert summary["expenses_by_category"][category1.id] == Decimal("100.00")
        assert category2.id not in summary["expenses_by_category"]

    def test_multi_month_summary(self, services):
        """Test summary across multiple months."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category = services.categories.create("Food", "Food expenses")

        # Create expenses in different months
        for month in [1, 2, 3]:
            t = Transaction.create_with_checksum(
                raw_data=f"0{month}/15/2024,Food{month},-{month * 100}.00,1000.00",
                account_id=account.id,
                transaction_date=date(2024, month, 15),
                post_date=None,
                description=f"Food {month}",
                bank_category=None,
                amount=Decimal(f"{month * 100}.00"),
                type="expense",
            )
            t.data_import_id = data_import.id
            t.category_id = category.id
            services.transactions.create(t)

        result = get_period_summary(
            services,
            date(2024, 1, 1),
            date(2024, 3, 31),
        )

        # Check each month
        assert result["cash_basis"]["2024/01"]["expense_total"] == Decimal("100.00")
        assert result["cash_basis"]["2024/02"]["expense_total"] == Decimal("200.00")
        assert result["cash_basis"]["2024/03"]["expense_total"] == Decimal("300.00")
