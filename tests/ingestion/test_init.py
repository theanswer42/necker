import pytest

from ingestion import get_ingestion_module, get_available_modules
import ingestion.amex as amex
import ingestion.bofa as bofa
import ingestion.chase as chase
import ingestion.discover as discover


class TestGetIngestionModule:
    """Tests for get_ingestion_module function."""

    def test_get_amex_module(self):
        """Test retrieving the amex module."""
        module = get_ingestion_module("amex")
        assert module == amex

    def test_get_bofa_module(self):
        """Test retrieving the bofa module."""
        module = get_ingestion_module("bofa")
        assert module == bofa

    def test_get_chase_module(self):
        """Test retrieving the chase module."""
        module = get_ingestion_module("chase")
        assert module == chase

    def test_get_discover_module(self):
        """Test retrieving the discover module."""
        module = get_ingestion_module("discover")
        assert module == discover

    def test_get_invalid_module_raises_error(self):
        """Test that requesting an unknown module raises ValueError."""
        with pytest.raises(ValueError, match="Unknown ingestion module: invalid"):
            get_ingestion_module("invalid")

    def test_get_case_sensitive(self):
        """Test that module names are case-sensitive."""
        with pytest.raises(ValueError, match="Unknown ingestion module: AMEX"):
            get_ingestion_module("AMEX")


class TestGetAvailableModules:
    """Tests for get_available_modules function."""

    def test_returns_all_modules(self):
        """Test that all expected modules are returned."""
        modules = get_available_modules()
        assert set(modules) == {"amex", "bofa", "chase", "discover"}

    def test_returns_list(self):
        """Test that the return value is a list."""
        modules = get_available_modules()
        assert isinstance(modules, list)

    def test_returns_strings(self):
        """Test that all returned values are strings."""
        modules = get_available_modules()
        assert all(isinstance(m, str) for m in modules)
