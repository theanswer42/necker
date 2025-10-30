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

        result = services.transactions.update_category(transaction.id, category.id)

        assert result is True

        # Verify it was updated
        found = services.transactions.find(transaction.id)
        assert found.category_id == category.id

    def test_update_category_nonexistent_transaction(self, services):
        """Test updating category for non-existent transaction returns False."""
        category = services.categories.create("Test", "Test category")

        result = services.transactions.update_category("nonexistent_id", category.id)

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

        count = services.transactions.batch_update_categories(transactions)

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

        count = services.transactions.batch_update_auto_categories(transactions)

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
        result = services.transactions.update_amortization(transaction.id, 12, end_date)

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

        count = services.transactions.batch_update_amortization(transactions)

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
                services.transactions.update_category(t.id, category.id)

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
