from datetime import date, timedelta
from decimal import Decimal

from models.transaction import Transaction


class TestTransactionService:
    """Tests for TransactionService."""

    def test_create_transaction(self, services):
        """Test creating a single transaction."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        transaction = Transaction.create_with_checksum(
            raw_data="01/15/2025,STARBUCKS,-5.75,1000.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
            post_date=None,
            description="STARBUCKS",
            bank_category=None,
            amount=Decimal("5.75"),
            type="expense",
        )
        transaction.data_import_id = data_import.id

        created = services.transactions.create(transaction)

        assert created.id == transaction.id
        assert created.account_id == account.id
        assert created.description == "STARBUCKS"
        assert created.amount == Decimal("5.75")

    def test_bulk_create_empty_list(self, services):
        """Test bulk creating with empty list returns 0."""
        count = services.transactions.bulk_create([])

        assert count == 0

    def test_bulk_create_multiple_transactions(self, services):
        """Test bulk creating multiple transactions."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        transactions = [
            Transaction.create_with_checksum(
                raw_data=f"01/15/2025,TX{i},-{i}.00,1000.00",
                account_id=account.id,
                transaction_date=date(2025, 1, 15),
                post_date=None,
                description=f"Transaction {i}",
                bank_category=None,
                amount=Decimal(str(i)),
                type="expense",
            )
            for i in range(1, 4)
        ]

        for t in transactions:
            t.data_import_id = data_import.id

        count = services.transactions.bulk_create(transactions)

        assert count >= 3  # total_changes is cumulative, so at least 3

        # Verify they were created
        found_transactions = services.transactions.find_by_account(account.id)
        assert len(found_transactions) == 3

    def test_bulk_create_with_duplicates_skips(self, services):
        """Test that bulk_create skips duplicate transactions."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        transaction = Transaction.create_with_checksum(
            raw_data="01/15/2025,DUPLICATE,-5.75,1000.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
            post_date=None,
            description="DUPLICATE",
            bank_category=None,
            amount=Decimal("5.75"),
            type="expense",
        )
        transaction.data_import_id = data_import.id

        # Create once
        services.transactions.create(transaction)

        # Count before
        before_count = len(services.transactions.find_by_account(account.id))

        # Try to bulk create with same transaction
        services.transactions.bulk_create([transaction])

        # Should skip the duplicate (INSERT OR IGNORE)
        after_count = len(services.transactions.find_by_account(account.id))
        assert after_count == before_count  # No new transactions added

    def test_find_transaction_by_id(self, services):
        """Test finding a transaction by ID."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        transaction = Transaction.create_with_checksum(
            raw_data="01/15/2025,FIND ME,-10.00,1000.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
            post_date=None,
            description="FIND ME",
            bank_category=None,
            amount=Decimal("10.00"),
            type="expense",
        )
        transaction.data_import_id = data_import.id
        services.transactions.create(transaction)

        found = services.transactions.find(transaction.id)

        assert found is not None
        assert found.id == transaction.id
        assert found.description == "FIND ME"

    def test_find_transaction_by_id_not_found(self, services):
        """Test finding a non-existent transaction returns None."""
        found = services.transactions.find("nonexistent_id")

        assert found is None

    def test_find_by_account(self, services):
        """Test finding all transactions for an account."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        transactions = [
            Transaction.create_with_checksum(
                raw_data=f"01/{15 + i}/2025,TX{i},-{i}.00,1000.00",
                account_id=account.id,
                transaction_date=date(2025, 1, 15 + i),
                post_date=None,
                description=f"Transaction {i}",
                bank_category=None,
                amount=Decimal(str(i)),
                type="expense",
            )
            for i in range(3)
        ]

        for t in transactions:
            t.data_import_id = data_import.id
            services.transactions.create(t)

        found = services.transactions.find_by_account(account.id)

        assert len(found) == 3
        # Should be ordered by date DESC
        assert found[0].transaction_date == date(2025, 1, 17)
        assert found[1].transaction_date == date(2025, 1, 16)
        assert found[2].transaction_date == date(2025, 1, 15)

    def test_find_by_account_empty(self, services):
        """Test finding transactions for account with no transactions."""
        account = services.accounts.create("test_account", "bofa", "Test Account")

        found = services.transactions.find_by_account(account.id)

        assert found == []

    def test_update_category(self, services):
        """Test updating a transaction's category."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category = services.categories.create("Groceries", "Food shopping")

        transaction = Transaction.create_with_checksum(
            raw_data="01/15/2025,STORE,-50.00,1000.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
            post_date=None,
            description="STORE",
            bank_category=None,
            amount=Decimal("50.00"),
            type="expense",
        )
        transaction.data_import_id = data_import.id
        services.transactions.create(transaction)

        transaction.category_id = category.id
        result = services.transactions.update(transaction, ["category_id"])

        assert result is True

        # Verify it was updated
        found = services.transactions.find(transaction.id)
        assert found.category_id == category.id

    def test_update_category_nonexistent_transaction(self, services):
        """Test updating category for non-existent transaction returns False."""
        category = services.categories.create("Test", "Test category")

        # Create a transaction object with non-existent ID
        fake_transaction = Transaction(
            id="nonexistent_id",
            account_id=999,
            transaction_date=date(2025, 1, 15),
            post_date=None,
            description="Fake",
            bank_category=None,
            amount=Decimal("10.00"),
            type="expense",
        )
        fake_transaction.category_id = category.id
        result = services.transactions.update(fake_transaction, ["category_id"])

        assert result is False

    def test_batch_update_categories(self, services):
        """Test batch updating categories for multiple transactions."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category = services.categories.create("Food", "Food expenses")

        transactions = []
        for i in range(3):
            t = Transaction.create_with_checksum(
                raw_data=f"01/1{5 + i}/2025,RESTAURANT{i},-20.00,1000.00",
                account_id=account.id,
                transaction_date=date(2025, 1, 15 + i),
                post_date=None,
                description=f"RESTAURANT{i}",
                bank_category=None,
                amount=Decimal("20.00"),
                type="expense",
            )
            t.data_import_id = data_import.id
            services.transactions.create(t)
            t.category_id = category.id
            transactions.append(t)

        count = services.transactions.batch_update(transactions, ["category_id"])

        assert count >= 3  # total_changes is cumulative

        # Verify all were updated
        for t in transactions:
            found = services.transactions.find(t.id)
            assert found.category_id == category.id

    def test_batch_update_auto_categories(self, services):
        """Test batch updating auto_category_id for multiple transactions."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category = services.categories.create("AutoCat", "Auto category")

        transactions = []
        for i in range(2):
            t = Transaction.create_with_checksum(
                raw_data=f"01/1{5 + i}/2025,AUTO{i},-10.00,1000.00",
                account_id=account.id,
                transaction_date=date(2025, 1, 15 + i),
                post_date=None,
                description=f"AUTO{i}",
                bank_category=None,
                amount=Decimal("10.00"),
                type="expense",
            )
            t.data_import_id = data_import.id
            services.transactions.create(t)
            t.auto_category_id = category.id
            transactions.append(t)

        count = services.transactions.batch_update(transactions, ["auto_category_id"])

        assert count >= 2  # total_changes is cumulative

        # Verify all were updated
        for t in transactions:
            found = services.transactions.find(t.id)
            assert found.auto_category_id == category.id

    def test_update_amortization(self, services):
        """Test updating amortization for a transaction."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        transaction = Transaction.create_with_checksum(
            raw_data="01/15/2025,SUBSCRIPTION,-120.00,1000.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
            post_date=None,
            description="SUBSCRIPTION",
            bank_category=None,
            amount=Decimal("120.00"),
            type="expense",
        )
        transaction.data_import_id = data_import.id
        services.transactions.create(transaction)

        end_date = date(2025, 12, 15)
        transaction.amortize_months = 12
        transaction.amortize_end_date = end_date
        result = services.transactions.update(
            transaction, ["amortize_months", "amortize_end_date"]
        )

        assert result is True

        # Verify it was updated
        found = services.transactions.find(transaction.id)
        assert found.amortize_months == 12
        assert found.amortize_end_date == end_date

    def test_batch_update_amortization(self, services):
        """Test batch updating amortization for multiple transactions."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        transactions = []
        for i in range(2):
            t = Transaction.create_with_checksum(
                raw_data=f"01/1{5 + i}/2025,SUB{i},-100.00,1000.00",
                account_id=account.id,
                transaction_date=date(2025, 1, 15 + i),
                post_date=None,
                description=f"SUBSCRIPTION{i}",
                bank_category=None,
                amount=Decimal("100.00"),
                type="expense",
            )
            t.data_import_id = data_import.id
            services.transactions.create(t)
            t.amortize_months = 10
            t.amortize_end_date = date(2025, 11, 15 + i)
            transactions.append(t)

        count = services.transactions.batch_update(
            transactions, ["amortize_months", "amortize_end_date"]
        )

        assert count >= 2  # total_changes is cumulative

        # Verify all were updated
        for t in transactions:
            found = services.transactions.find(t.id)
            assert found.amortize_months == 10

    def test_get_transactions_by_date_range(self, services):
        """Test getting transactions by date range."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Create transactions across multiple months
        dates = [date(2025, 1, 15), date(2025, 2, 15), date(2025, 3, 15)]
        for i, txn_date in enumerate(dates):
            t = Transaction.create_with_checksum(
                raw_data=f"{txn_date.isoformat()},TX{i},-10.00,1000.00",
                account_id=account.id,
                transaction_date=txn_date,
                post_date=None,
                description=f"Transaction {i}",
                bank_category=None,
                amount=Decimal("10.00"),
                type="expense",
            )
            t.data_import_id = data_import.id
            services.transactions.create(t)

        # Get transactions for February
        found = services.transactions.get_transactions_by_date_range(
            "2025-02-01", "2025-02-28"
        )

        assert len(found) == 1
        assert found[0].transaction_date == date(2025, 2, 15)

    def test_get_transactions_by_date_range_with_account_filter(self, services):
        """Test getting transactions by date range filtered by account."""
        account1 = services.accounts.create("account1", "bofa", "Account 1")
        account2 = services.accounts.create("account2", "chase", "Account 2")
        data_import1 = services.data_imports.create(account1.id, "test1.csv.gz")
        data_import2 = services.data_imports.create(account2.id, "test2.csv.gz")

        # Create transactions for both accounts on the same date
        for account, data_import in [
            (account1, data_import1),
            (account2, data_import2),
        ]:
            t = Transaction.create_with_checksum(
                raw_data=f"2025-01-15,TX-{account.id},-10.00,1000.00",
                account_id=account.id,
                transaction_date=date(2025, 1, 15),
                post_date=None,
                description=f"Transaction for {account.name}",
                bank_category=None,
                amount=Decimal("10.00"),
                type="expense",
            )
            t.data_import_id = data_import.id
            services.transactions.create(t)

        # Get transactions for account1 only
        found = services.transactions.get_transactions_by_date_range(
            "2025-01-01", "2025-01-31", account_id=account1.id
        )

        assert len(found) == 1
        assert found[0].account_id == account1.id

    def test_get_transactions_by_month(self, services):
        """Test getting transactions by month."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Create transactions in January and February
        dates = [date(2025, 1, 15), date(2025, 1, 20), date(2025, 2, 10)]
        for i, txn_date in enumerate(dates):
            t = Transaction.create_with_checksum(
                raw_data=f"{txn_date.isoformat()},TX{i},-10.00,1000.00",
                account_id=account.id,
                transaction_date=txn_date,
                post_date=None,
                description=f"Transaction {i}",
                bank_category=None,
                amount=Decimal("10.00"),
                type="expense",
            )
            t.data_import_id = data_import.id
            services.transactions.create(t)

        # Get transactions for January 2025
        found = services.transactions.get_transactions_by_month(2025, 1)

        assert len(found) == 2
        assert all(t.transaction_date.month == 1 for t in found)

    def test_find_historical_for_categorization(self, services):
        """Test finding historical categorized transactions."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category = services.categories.create("Food", "Food expenses")

        # Create transactions with different dates and categories
        today = date.today()
        dates = [
            today - timedelta(days=30),  # Within 90 days, has category
            today - timedelta(days=60),  # Within 90 days, has category
            today - timedelta(days=100),  # Outside 90 days, has category
            today - timedelta(days=30),  # Within 90 days, no category
        ]

        for i, txn_date in enumerate(dates):
            t = Transaction.create_with_checksum(
                raw_data=f"{txn_date.isoformat()},TX{i},-10.00,1000.00",
                account_id=account.id,
                transaction_date=txn_date,
                post_date=None,
                description=f"Transaction {i}",
                bank_category=None,
                amount=Decimal("10.00"),
                type="expense",
            )
            t.data_import_id = data_import.id
            services.transactions.create(t)

            # Set category for first 3 transactions only
            if i < 3:
                t.category_id = category.id
                services.transactions.update(t, ["category_id"])

        # Find historical categorized transactions
        found = services.transactions.find_historical_for_categorization(
            account.id, days=90
        )

        # Should only return transactions within 90 days that have a category
        assert len(found) == 2

    def test_transaction_with_metadata(self, services):
        """Test creating and retrieving transaction with additional metadata."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        metadata = {"running_balance": "1234.56", "reference": "REF123"}
        transaction = Transaction.create_with_checksum(
            raw_data="01/15/2025,STORE,-50.00,1234.56",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
            post_date=None,
            description="STORE",
            bank_category=None,
            amount=Decimal("50.00"),
            type="expense",
            additional_metadata=metadata,
        )
        transaction.data_import_id = data_import.id
        services.transactions.create(transaction)

        found = services.transactions.find(transaction.id)

        assert found.additional_metadata == metadata

    def test_transaction_with_post_date(self, services):
        """Test creating transaction with post_date."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        transaction = Transaction.create_with_checksum(
            raw_data="01/15/2025,01/16/2025,PENDING,-25.00,1000.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
            post_date=date(2025, 1, 16),
            description="PENDING",
            bank_category="Shopping",
            amount=Decimal("25.00"),
            type="expense",
        )
        transaction.data_import_id = data_import.id
        services.transactions.create(transaction)

        found = services.transactions.find(transaction.id)

        assert found.post_date == date(2025, 1, 16)
        assert found.bank_category == "Shopping"

    def test_get_transactions_by_date_range_exclude_amortized(self, services):
        """Test filtering out amortized transactions."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Create amortized transaction
        t1 = Transaction.create_with_checksum(
            raw_data="01/15/2025,Subscription,-100.00,1000.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
            post_date=None,
            description="Annual Subscription",
            bank_category=None,
            amount=Decimal("100.00"),
            type="expense",
        )
        t1.data_import_id = data_import.id
        t1.amortize_months = 12
        services.transactions.create(t1)

        # Create regular transaction
        t2 = Transaction.create_with_checksum(
            raw_data="01/20/2025,Coffee,-5.00,995.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 20),
            post_date=None,
            description="Coffee",
            bank_category=None,
            amount=Decimal("5.00"),
            type="expense",
        )
        t2.data_import_id = data_import.id
        services.transactions.create(t2)

        # Get all transactions
        all_txns = services.transactions.get_transactions_by_date_range(
            "2025-01-01", "2025-01-31"
        )
        assert len(all_txns) == 2

        # Exclude amortized
        non_amortized = services.transactions.get_transactions_by_date_range(
            "2025-01-01", "2025-01-31", exclude_amortized=True
        )
        assert len(non_amortized) == 1
        assert non_amortized[0].description == "Coffee"

    def test_get_transactions_by_date_range_filter_categories(self, services):
        """Test filtering by category IDs."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category1 = services.categories.create("Food", "Food expenses")
        category2 = services.categories.create("Transport", "Transport")

        # Create transaction with category1
        t1 = Transaction.create_with_checksum(
            raw_data="01/15/2025,Coffee,-5.00,1000.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
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
            raw_data="01/20/2025,Bus,-2.00,998.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 20),
            post_date=None,
            description="Bus",
            bank_category=None,
            amount=Decimal("2.00"),
            type="expense",
        )
        t2.data_import_id = data_import.id
        t2.category_id = category2.id
        services.transactions.create(t2)

        # Create transaction without category
        t3 = Transaction.create_with_checksum(
            raw_data="01/22/2025,Other,-3.00,995.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 22),
            post_date=None,
            description="Other",
            bank_category=None,
            amount=Decimal("3.00"),
            type="expense",
        )
        t3.data_import_id = data_import.id
        services.transactions.create(t3)

        # Get all transactions
        all_txns = services.transactions.get_transactions_by_date_range(
            "2025-01-01", "2025-01-31"
        )
        assert len(all_txns) == 3

        # Filter by single category
        food_txns = services.transactions.get_transactions_by_date_range(
            "2025-01-01", "2025-01-31", category_ids=[category1.id]
        )
        assert len(food_txns) == 1
        assert food_txns[0].description == "Coffee"

        # Filter by multiple categories
        multi_category = services.transactions.get_transactions_by_date_range(
            "2025-01-01", "2025-01-31", category_ids=[category1.id, category2.id]
        )
        assert len(multi_category) == 2

        # Empty category list should return all
        empty_filter = services.transactions.get_transactions_by_date_range(
            "2025-01-01", "2025-01-31", category_ids=[]
        )
        assert len(empty_filter) == 3

    def test_get_transactions_by_date_range_combined_filters(self, services):
        """Test combining exclude_amortized and category filters."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category1 = services.categories.create("Food", "Food expenses")

        # Create amortized transaction with category1
        t1 = Transaction.create_with_checksum(
            raw_data="01/15/2025,Subscription,-100.00,1000.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
            post_date=None,
            description="Food Subscription",
            bank_category=None,
            amount=Decimal("100.00"),
            type="expense",
        )
        t1.data_import_id = data_import.id
        t1.category_id = category1.id
        t1.amortize_months = 12
        services.transactions.create(t1)

        # Create regular transaction with category1
        t2 = Transaction.create_with_checksum(
            raw_data="01/20/2025,Coffee,-5.00,995.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 20),
            post_date=None,
            description="Coffee",
            bank_category=None,
            amount=Decimal("5.00"),
            type="expense",
        )
        t2.data_import_id = data_import.id
        t2.category_id = category1.id
        services.transactions.create(t2)

        # Get Food category, exclude amortized
        filtered = services.transactions.get_transactions_by_date_range(
            "2025-01-01",
            "2025-01-31",
            exclude_amortized=True,
            category_ids=[category1.id],
        )
        assert len(filtered) == 1
        assert filtered[0].description == "Coffee"

    def test_get_transactions_by_month_with_filters(self, services):
        """Test get_transactions_by_month with new filter parameters."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")
        category1 = services.categories.create("Food", "Food expenses")

        # Create amortized transaction
        t1 = Transaction.create_with_checksum(
            raw_data="01/15/2025,Subscription,-100.00,1000.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
            post_date=None,
            description="Subscription",
            bank_category=None,
            amount=Decimal("100.00"),
            type="expense",
        )
        t1.data_import_id = data_import.id
        t1.amortize_months = 12
        services.transactions.create(t1)

        # Create regular transaction with category
        t2 = Transaction.create_with_checksum(
            raw_data="01/20/2025,Coffee,-5.00,995.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 20),
            post_date=None,
            description="Coffee",
            bank_category=None,
            amount=Decimal("5.00"),
            type="expense",
        )
        t2.data_import_id = data_import.id
        t2.category_id = category1.id
        services.transactions.create(t2)

        # Get all for month
        all_month = services.transactions.get_transactions_by_month(2025, 1)
        assert len(all_month) == 2

        # Exclude amortized
        non_amortized = services.transactions.get_transactions_by_month(
            2025, 1, exclude_amortized=True
        )
        assert len(non_amortized) == 1

        # Filter by category
        food_only = services.transactions.get_transactions_by_month(
            2025, 1, category_ids=[category1.id]
        )
        assert len(food_only) == 1
        assert food_only[0].description == "Coffee"

    def test_get_accrued_transactions_by_month_basic(self, services):
        """Test getting accrued transactions for a month."""
        from dateutil.relativedelta import relativedelta

        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Create transaction on Jan 15, 2024 with 12 month amortization
        # This should accrue in Jan 2024 - Dec 2024
        t1 = Transaction.create_with_checksum(
            raw_data="01/15/2024,Annual Subscription,-120.00,1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Annual Subscription",
            bank_category=None,
            amount=Decimal("120.00"),
            type="expense",
        )
        t1.data_import_id = data_import.id
        t1.amortize_months = 12
        t1.amortize_end_date = t1.transaction_date + relativedelta(months=11, day=31)
        services.transactions.create(t1)

        # Get accrued for July 2024 (should include the transaction)
        accrued = services.transactions.get_accrued_transactions_by_month(2024, 7)

        assert len(accrued) == 1
        assert accrued[0].id == t1.id
        assert accrued[0].amount == Decimal("10.00")  # 120 / 12 = 10
        assert accrued[0].transaction_date == date(2024, 7, 1)  # Start of month
        assert accrued[0].accrued is True
        assert accrued[0].description == "Annual Subscription"

    def test_get_accrued_transactions_by_month_boundary_dates(self, services):
        """Test accrual boundaries - first and last months."""
        from dateutil.relativedelta import relativedelta

        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Transaction on Jan 15, 2024, amortize for 12 months
        # End date: Dec 31, 2024
        t1 = Transaction.create_with_checksum(
            raw_data="01/15/2024,Subscription,-120.00,1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Subscription",
            bank_category=None,
            amount=Decimal("120.00"),
            type="expense",
        )
        t1.data_import_id = data_import.id
        t1.amortize_months = 12
        t1.amortize_end_date = t1.transaction_date + relativedelta(months=11, day=31)
        services.transactions.create(t1)

        # Should accrue in January 2024 (first month)
        jan_accrued = services.transactions.get_accrued_transactions_by_month(2024, 1)
        assert len(jan_accrued) == 1

        # Should accrue in December 2024 (last month)
        dec_accrued = services.transactions.get_accrued_transactions_by_month(2024, 12)
        assert len(dec_accrued) == 1

        # Should NOT accrue in January 2025 (after end date)
        jan_2025_accrued = services.transactions.get_accrued_transactions_by_month(
            2025, 1
        )
        assert len(jan_2025_accrued) == 0

    def test_get_accrued_transactions_by_month_amount_rounding(self, services):
        """Test that accrued amounts are rounded to 2 decimals."""
        from dateutil.relativedelta import relativedelta

        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Amount that doesn't divide evenly: 100 / 3 = 33.333...
        t1 = Transaction.create_with_checksum(
            raw_data="01/01/2024,Quarterly,-100.00,1000.00",
            account_id=account.id,
            transaction_date=date(2024, 1, 1),
            post_date=None,
            description="Quarterly",
            bank_category=None,
            amount=Decimal("100.00"),
            type="expense",
        )
        t1.data_import_id = data_import.id
        t1.amortize_months = 3
        t1.amortize_end_date = t1.transaction_date + relativedelta(months=2, day=31)
        services.transactions.create(t1)

        accrued = services.transactions.get_accrued_transactions_by_month(2024, 1)

        assert len(accrued) == 1
        assert accrued[0].amount == Decimal("33.33")  # Rounded to 2 decimals

    def test_get_accrued_transactions_by_month_with_filters(self, services):
        """Test filtering accrued transactions by account and category."""
        from dateutil.relativedelta import relativedelta

        account1 = services.accounts.create("account1", "bofa", "Account 1")
        account2 = services.accounts.create("account2", "chase", "Account 2")
        data_import1 = services.data_imports.create(account1.id, "test1.csv.gz")
        data_import2 = services.data_imports.create(account2.id, "test2.csv.gz")
        category1 = services.categories.create("Software", "Software subscriptions")
        category2 = services.categories.create("Entertainment", "Entertainment")

        # Transaction in account1 with category1
        t1 = Transaction.create_with_checksum(
            raw_data="01/01/2024,Software,-120.00,1000.00",
            account_id=account1.id,
            transaction_date=date(2024, 1, 1),
            post_date=None,
            description="Software",
            bank_category=None,
            amount=Decimal("120.00"),
            type="expense",
        )
        t1.data_import_id = data_import1.id
        t1.category_id = category1.id
        t1.amortize_months = 12
        t1.amortize_end_date = t1.transaction_date + relativedelta(months=11, day=31)
        services.transactions.create(t1)

        # Transaction in account2 with category2
        t2 = Transaction.create_with_checksum(
            raw_data="01/01/2024,Streaming,-60.00,1000.00",
            account_id=account2.id,
            transaction_date=date(2024, 1, 1),
            post_date=None,
            description="Streaming",
            bank_category=None,
            amount=Decimal("60.00"),
            type="expense",
        )
        t2.data_import_id = data_import2.id
        t2.category_id = category2.id
        t2.amortize_months = 12
        t2.amortize_end_date = t2.transaction_date + relativedelta(months=11, day=31)
        services.transactions.create(t2)

        # Get all accrued
        all_accrued = services.transactions.get_accrued_transactions_by_month(2024, 6)
        assert len(all_accrued) == 2

        # Filter by account
        account1_accrued = services.transactions.get_accrued_transactions_by_month(
            2024, 6, account_id=account1.id
        )
        assert len(account1_accrued) == 1
        assert account1_accrued[0].description == "Software"

        # Filter by category
        category1_accrued = services.transactions.get_accrued_transactions_by_month(
            2024, 6, category_ids=[category1.id]
        )
        assert len(category1_accrued) == 1
        assert category1_accrued[0].description == "Software"

        # Filter by multiple categories
        multi_category = services.transactions.get_accrued_transactions_by_month(
            2024, 6, category_ids=[category1.id, category2.id]
        )
        assert len(multi_category) == 2

    def test_get_accrued_transactions_excludes_non_amortized(self, services):
        """Test that non-amortized transactions are not included."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Regular transaction without amortization
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
        services.transactions.create(t1)

        # Get accrued for January 2024
        accrued = services.transactions.get_accrued_transactions_by_month(2024, 1)

        # Should be empty since transaction has no amortization
        assert len(accrued) == 0

    def test_create_transaction_with_merchant_name(self, services):
        """Test creating a transaction with merchant_name fields."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        transaction = Transaction.create_with_checksum(
            raw_data="01/15/2025,AMAZON.COM*123ABC,-25.00,1000.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
            post_date=None,
            description="AMAZON.COM*123ABC",
            bank_category=None,
            amount=Decimal("25.00"),
            type="expense",
        )
        transaction.data_import_id = data_import.id
        transaction.merchant_name = "Amazon"
        transaction.auto_merchant_name = "Amazon"

        created = services.transactions.create(transaction)

        # Retrieve and verify
        found = services.transactions.find(created.id)
        assert found is not None
        assert found.merchant_name == "Amazon"
        assert found.auto_merchant_name == "Amazon"

    def test_batch_update_merchant_names(self, services):
        """Test batch updating merchant_name and auto_merchant_name."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        # Create transactions
        t1 = Transaction.create_with_checksum(
            raw_data="01/15/2025,AMAZON.COM,-25.00,1000.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
            post_date=None,
            description="AMAZON.COM",
            bank_category=None,
            amount=Decimal("25.00"),
            type="expense",
        )
        t1.data_import_id = data_import.id
        services.transactions.create(t1)

        t2 = Transaction.create_with_checksum(
            raw_data="01/20/2025,STARBUCKS,-5.00,995.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 20),
            post_date=None,
            description="STARBUCKS",
            bank_category=None,
            amount=Decimal("5.00"),
            type="expense",
        )
        t2.data_import_id = data_import.id
        services.transactions.create(t2)

        # Update merchant names
        t1.merchant_name = "Amazon"
        t2.merchant_name = "Starbucks"

        updated_count = services.transactions.batch_update([t1, t2], ["merchant_name"])

        assert updated_count == 2

        # Verify updates
        found_t1 = services.transactions.find(t1.id)
        found_t2 = services.transactions.find(t2.id)

        assert found_t1.merchant_name == "Amazon"
        assert found_t2.merchant_name == "Starbucks"

    def test_batch_update_auto_merchant_names(self, services):
        """Test batch updating auto_merchant_name."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        data_import = services.data_imports.create(account.id, "test.csv.gz")

        t1 = Transaction.create_with_checksum(
            raw_data="01/15/2025,WAL-MART #123,-50.00,1000.00",
            account_id=account.id,
            transaction_date=date(2025, 1, 15),
            post_date=None,
            description="WAL-MART #123",
            bank_category=None,
            amount=Decimal("50.00"),
            type="expense",
        )
        t1.data_import_id = data_import.id
        services.transactions.create(t1)

        # Update auto_merchant_name
        t1.auto_merchant_name = "Walmart"

        updated_count = services.transactions.batch_update([t1], ["auto_merchant_name"])

        assert updated_count == 1

        # Verify
        found = services.transactions.find(t1.id)
        assert found.auto_merchant_name == "Walmart"
