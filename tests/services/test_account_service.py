"""Tests for services/accounts.py AccountService."""

import pytest

from services.accounts import AccountService


class TestCreateAccount:
    def _svc(self, services):
        return AccountService(services.db_manager)

    def test_happy_path(self, services):
        account = self._svc(services).create_account(
            "bofa_checking", "bofa", "BofA Checking"
        )
        assert account.id is not None
        assert account.name == "bofa_checking"
        assert account.account_type == "bofa"
        assert account.description == "BofA Checking"

    def test_integration_find_after_create(self, services):
        self._svc(services).create_account("chase_savings", "chase", "Chase Savings")
        found = services.accounts.find_by_name("chase_savings")
        assert found is not None
        assert found.account_type == "chase"

    def test_invalid_name_uppercase(self, services):
        with pytest.raises(ValueError, match="invalid"):
            self._svc(services).create_account("BofA", "bofa", "BofA Checking")

    def test_invalid_name_spaces(self, services):
        with pytest.raises(ValueError, match="invalid"):
            self._svc(services).create_account("my account", "bofa", "My Account")

    def test_invalid_name_digits(self, services):
        with pytest.raises(ValueError, match="invalid"):
            self._svc(services).create_account("account1", "bofa", "Account 1")

    def test_invalid_name_empty(self, services):
        with pytest.raises(ValueError, match="invalid"):
            self._svc(services).create_account("", "bofa", "My Account")

    def test_invalid_account_type(self, services):
        with pytest.raises(ValueError, match="Invalid account type"):
            self._svc(services).create_account(
                "my_account", "unknown_bank", "My Account"
            )

    def test_invalid_account_type_lists_valid_types(self, services):
        with pytest.raises(ValueError, match="bofa"):
            self._svc(services).create_account("my_account", "bad_type", "My Account")

    def test_empty_description(self, services):
        with pytest.raises(ValueError, match="Description cannot be empty"):
            self._svc(services).create_account("my_account", "bofa", "")

    def test_whitespace_only_description(self, services):
        with pytest.raises(ValueError, match="Description cannot be empty"):
            self._svc(services).create_account("my_account", "bofa", "   ")

    def test_duplicate_name(self, services):
        svc = self._svc(services)
        svc.create_account("my_account", "bofa", "First")
        with pytest.raises(ValueError, match="already exists"):
            svc.create_account("my_account", "chase", "Second")

    def test_duplicate_name_error_message_includes_name(self, services):
        svc = self._svc(services)
        svc.create_account("dupe_account", "bofa", "First")
        with pytest.raises(ValueError, match="dupe_account"):
            svc.create_account("dupe_account", "chase", "Second")

    def test_underscore_name_valid(self, services):
        account = self._svc(services).create_account(
            "my_checking_account", "bofa", "My Account"
        )
        assert account.name == "my_checking_account"

    def test_single_letter_name_valid(self, services):
        account = self._svc(services).create_account("a", "bofa", "Single letter")
        assert account.name == "a"
