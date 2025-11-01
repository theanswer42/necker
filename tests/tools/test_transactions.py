"""Tests for transaction analysis tools."""

from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from models.transaction import Transaction
from tools.transactions import get_period_transactions


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

        assert "2024/01" in result
        assert len(result) == 1

        # Cash basis should have only the regular transaction
        cash_basis = result["2024/01"]["cash_basis"]
        assert len(cash_basis) == 1
        assert cash_basis[0].description == "Coffee"

        # Accrual basis should have the amortized transaction
        accrual_basis = result["2024/01"]["accrual_basis"]
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

        assert len(result) == 3
        assert "2024/01" in result
        assert "2024/02" in result
        assert "2024/03" in result

        # Each month should have one cash basis transaction
        for month_key in ["2024/01", "2024/02", "2024/03"]:
            assert len(result[month_key]["cash_basis"]) == 1
            assert len(result[month_key]["accrual_basis"]) == 0

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

        assert len(result) == 3
        assert "2024/11" in result
        assert "2024/12" in result
        assert "2025/01" in result

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
        cash_basis = result["2024/01"]["cash_basis"]
        assert len(cash_basis) == 1
        assert cash_basis[0].description == "Coffee"

        accrual_basis = result["2024/01"]["accrual_basis"]
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

        assert len(result) == 3
        assert "2024/01" in result
        assert "2024/02" in result
        assert "2024/03" in result

        # January has transactions
        assert len(result["2024/01"]["cash_basis"]) == 1

        # February and March are empty
        assert len(result["2024/02"]["cash_basis"]) == 0
        assert len(result["2024/02"]["accrual_basis"]) == 0
        assert len(result["2024/03"]["cash_basis"]) == 0
        assert len(result["2024/03"]["accrual_basis"]) == 0

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
        assert len(result["2024/01"]["accrual_basis"]) == 1
        assert result["2024/01"]["accrual_basis"][0].amount == Decimal("100.00")

        assert len(result["2024/02"]["accrual_basis"]) == 1
        assert result["2024/02"]["accrual_basis"][0].amount == Decimal("100.00")

        assert len(result["2024/03"]["accrual_basis"]) == 1
        assert result["2024/03"]["accrual_basis"][0].amount == Decimal("100.00")

        assert len(result["2024/04"]["accrual_basis"]) == 0
