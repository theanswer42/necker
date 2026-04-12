"""Tests for services/accounts.py create_account function."""

import pytest

from services.accounts import create_account


class TestCreateAccount:
    def test_happy_path(self, services):
        account = create_account(services, "bofa_checking", "bofa", "BofA Checking")
        assert account.id is not None
        assert account.name == "bofa_checking"
        assert account.account_type == "bofa"
        assert account.description == "BofA Checking"

    def test_integration_find_after_create(self, services):
        create_account(services, "chase_savings", "chase", "Chase Savings")
        found = services.accounts.find_by_name("chase_savings")
        assert found is not None
        assert found.account_type == "chase"

    def test_invalid_name_uppercase(self, services):
        with pytest.raises(ValueError, match="invalid"):
            create_account(services, "BofA", "bofa", "BofA Checking")

    def test_invalid_name_spaces(self, services):
        with pytest.raises(ValueError, match="invalid"):
            create_account(services, "my account", "bofa", "My Account")

    def test_invalid_name_digits(self, services):
        with pytest.raises(ValueError, match="invalid"):
            create_account(services, "account1", "bofa", "Account 1")

    def test_invalid_name_empty(self, services):
        with pytest.raises(ValueError, match="invalid"):
            create_account(services, "", "bofa", "My Account")

    def test_invalid_account_type(self, services):
        with pytest.raises(ValueError, match="Invalid account type"):
            create_account(services, "my_account", "unknown_bank", "My Account")

    def test_invalid_account_type_lists_valid_types(self, services):
        with pytest.raises(ValueError, match="bofa"):
            create_account(services, "my_account", "bad_type", "My Account")

    def test_empty_description(self, services):
        with pytest.raises(ValueError, match="Description cannot be empty"):
            create_account(services, "my_account", "bofa", "")

    def test_whitespace_only_description(self, services):
        with pytest.raises(ValueError, match="Description cannot be empty"):
            create_account(services, "my_account", "bofa", "   ")

    def test_duplicate_name(self, services):
        create_account(services, "my_account", "bofa", "First")
        with pytest.raises(ValueError, match="already exists"):
            create_account(services, "my_account", "chase", "Second")

    def test_duplicate_name_error_message_includes_name(self, services):
        create_account(services, "dupe_account", "bofa", "First")
        with pytest.raises(ValueError, match="dupe_account"):
            create_account(services, "dupe_account", "chase", "Second")

    def test_underscore_name_valid(self, services):
        account = create_account(services, "my_checking_account", "bofa", "My Account")
        assert account.name == "my_checking_account"

    def test_single_letter_name_valid(self, services):
        account = create_account(services, "a", "bofa", "Single letter")
        assert account.name == "a"
