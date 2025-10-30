import pytest
import sqlite3


class TestAccountService:
    """Tests for AccountService."""

    def test_create_account(self, services):
        """Test creating a new account."""
        account = services.accounts.create(
            "bofa_checking", "bofa", "Bank of America Checking"
        )

        assert account.id is not None
        assert account.id > 0
        assert account.name == "bofa_checking"
        assert account.type == "bofa"
        assert account.description == "Bank of America Checking"

    def test_find_account_by_id(self, services):
        """Test finding an account by ID."""
        # Create an account first
        created = services.accounts.create("chase_card", "chase", "Chase Sapphire Card")

        # Find it by ID
        found = services.accounts.find(created.id)

        assert found is not None
        assert found.id == created.id
        assert found.name == "chase_card"
        assert found.type == "chase"
        assert found.description == "Chase Sapphire Card"

    def test_find_account_by_id_not_found(self, services):
        """Test finding a non-existent account by ID returns None."""
        found = services.accounts.find(9999)

        assert found is None

    def test_find_by_name(self, services):
        """Test finding an account by name."""
        # Create an account first
        services.accounts.create("amex_card", "amex", "American Express Card")

        # Find it by name
        found = services.accounts.find_by_name("amex_card")

        assert found is not None
        assert found.name == "amex_card"
        assert found.type == "amex"
        assert found.description == "American Express Card"

    def test_find_by_name_not_found(self, services):
        """Test finding a non-existent account by name returns None."""
        found = services.accounts.find_by_name("nonexistent")

        assert found is None

    def test_find_by_name_case_sensitive(self, services):
        """Test that account name lookup is case-sensitive."""
        services.accounts.create("test_account", "bofa", "Test Account")

        # Try finding with different case
        found = services.accounts.find_by_name("Test_Account")

        assert found is None

    def test_find_all_empty(self, services):
        """Test finding all accounts when database is empty."""
        accounts = services.accounts.find_all()

        assert accounts == []
        assert isinstance(accounts, list)

    def test_find_all_single_account(self, services):
        """Test finding all accounts with one account."""
        created = services.accounts.create("single", "bofa", "Single Account")

        accounts = services.accounts.find_all()

        assert len(accounts) == 1
        assert accounts[0].id == created.id
        assert accounts[0].name == "single"

    def test_find_all_multiple_accounts(self, services):
        """Test finding all accounts with multiple accounts."""
        account1 = services.accounts.create("account1", "bofa", "First Account")
        account2 = services.accounts.create("account2", "chase", "Second Account")
        account3 = services.accounts.create("account3", "amex", "Third Account")

        accounts = services.accounts.find_all()

        assert len(accounts) == 3
        # Verify they're ordered by ID
        assert accounts[0].id == account1.id
        assert accounts[1].id == account2.id
        assert accounts[2].id == account3.id

    def test_find_all_returns_correct_order(self, services):
        """Test that find_all returns accounts ordered by ID."""
        # Create accounts in random order
        services.accounts.create("zebra", "bofa", "Zebra")
        services.accounts.create("alpha", "chase", "Alpha")
        services.accounts.create("beta", "amex", "Beta")

        accounts = services.accounts.find_all()

        # Should be ordered by ID (creation order), not name
        assert accounts[0].name == "zebra"
        assert accounts[1].name == "alpha"
        assert accounts[2].name == "beta"

    def test_create_duplicate_name_raises_error(self, services):
        """Test that creating an account with duplicate name raises an error."""
        # Create first account
        services.accounts.create("duplicate", "bofa", "First")

        # Try to create another with the same name
        with pytest.raises(sqlite3.IntegrityError):
            services.accounts.create("duplicate", "chase", "Second")

    def test_delete_account(self, services):
        """Test deleting an account."""
        # Create an account
        account = services.accounts.create("to_delete", "bofa", "Will be deleted")

        # Delete it
        result = services.accounts.delete(account.id)

        assert result is True

        # Verify it's gone
        found = services.accounts.find(account.id)
        assert found is None

    def test_delete_nonexistent_account(self, services):
        """Test deleting a non-existent account returns False."""
        result = services.accounts.delete(9999)

        assert result is False

    def test_delete_does_not_affect_other_accounts(self, services):
        """Test that deleting one account doesn't affect others."""
        account1 = services.accounts.create("keep1", "bofa", "Keep This")
        account2 = services.accounts.create("delete_me", "chase", "Delete This")
        account3 = services.accounts.create("keep2", "amex", "Keep This Too")

        # Delete the middle account
        services.accounts.delete(account2.id)

        # Verify the others still exist
        remaining = services.accounts.find_all()
        assert len(remaining) == 2
        assert remaining[0].id == account1.id
        assert remaining[1].id == account3.id

    def test_account_to_dict(self, services):
        """Test that Account.to_dict() works correctly."""
        account = services.accounts.create("test", "bofa", "Test Account")

        account_dict = account.to_dict()

        assert account_dict == {
            "id": account.id,
            "name": "test",
            "type": "bofa",
            "description": "Test Account",
        }

    def test_create_account_with_special_characters(self, services):
        """Test creating account with special characters in description."""
        account = services.accounts.create(
            "special",
            "bofa",
            "Account with 'quotes' and \"double quotes\" & special chars!",
        )

        found = services.accounts.find(account.id)
        assert (
            found.description
            == "Account with 'quotes' and \"double quotes\" & special chars!"
        )

    def test_create_account_with_empty_description(self, services):
        """Test creating account with empty description."""
        account = services.accounts.create("empty_desc", "bofa", "")

        found = services.accounts.find(account.id)
        assert found.description == ""

    def test_multiple_accounts_different_types(self, services):
        """Test creating multiple accounts with different types."""
        services.accounts.create("bofa1", "bofa", "BofA Account")
        services.accounts.create("chase1", "chase", "Chase Account")
        services.accounts.create("amex1", "amex", "Amex Account")
        services.accounts.create("discover1", "discover", "Discover Account")

        accounts = services.accounts.find_all()
        assert len(accounts) == 4

        # Verify all types are preserved
        types = {acc.type for acc in accounts}
        assert types == {"bofa", "chase", "amex", "discover"}
