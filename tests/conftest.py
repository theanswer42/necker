"""Shared pytest fixtures for all tests."""

import io
import sqlite3
import pytest
from pathlib import Path

from cli.output import OutputWriter, TextRenderer
from config import Config, get_migrations_dir
from repositories.accounts import AccountRepository
from repositories.budgets import BudgetRepository
from repositories.categories import CategoryRepository
from repositories.data_imports import DataImportRepository
from repositories.transactions import TransactionRepository
from tests.helpers import run_migrations


@pytest.fixture
def output():
    """Provide a quiet OutputWriter that discards its output.

    Tests that assert on rendered text should construct their own writer
    with an explicit StringIO stream.
    """
    return OutputWriter(TextRenderer(stream=io.StringIO()))


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing.

    Yields:
        sqlite3.Connection: Connection to in-memory database.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


@pytest.fixture
def test_config(tmp_path):
    """Create a test configuration pointing to a temporary database.

    Args:
        tmp_path: pytest tmp_path fixture for temporary directory.

    Returns:
        Config: Test configuration object.
    """
    return Config(
        base_dir=tmp_path / "necker",
        db_data_dir=tmp_path / "necker" / "db",
        db_filename="test.db",
        log_level="DEBUG",
        log_dir=tmp_path / "necker" / "logs",
        archive_enabled=False,
        archive_dir=tmp_path / "necker" / "archives",
        enable_reset=False,
        llm_enabled=False,
        llm_provider="openai",
        llm_openai_api_key="",
        llm_openai_model="gpt-4o-mini",
    )


@pytest.fixture
def db_manager_with_schema(test_db):
    """Create a DatabaseManager with schema already set up.

    This fixture provides a DatabaseManager that uses an in-memory database
    with all migrations already applied.

    Args:
        test_db: In-memory database connection fixture.

    Returns:
        DatabaseManager: Database manager with schema ready.
    """
    # Run migrations to set up schema
    migrations_dir = get_migrations_dir()
    run_migrations(test_db, migrations_dir)

    # Create a custom DatabaseManager that uses our in-memory connection
    class TestDatabaseManager:
        """Test database manager that uses in-memory connection."""

        def __init__(self, conn):
            self.conn = conn

        def connect(self):
            """Return a context manager for the test connection."""
            return _TestConnectionContext(self.conn)

        def get_db_path(self):
            """Return a fake path for the test database."""
            return Path(":memory:")

        def get_migrations_dir(self):
            """Get the migrations directory path."""
            return get_migrations_dir()

    class _TestConnectionContext:
        """Context manager for test database connections."""

        def __init__(self, conn):
            self.conn = conn

        def __enter__(self):
            return self.conn

        def __exit__(self, exc_type, exc_val, exc_tb):
            # Don't close the connection - let the fixture handle it
            pass

    return TestDatabaseManager(test_db)


@pytest.fixture
def services(test_config, db_manager_with_schema):
    """Provide repository access and config for tests.

    This is a lightweight shim that gives tests access to repositories
    and config via a simple namespace object.
    """

    class _TestServices:
        def __init__(self):
            self.config = test_config
            self.db_manager = db_manager_with_schema
            self.accounts = AccountRepository(db_manager_with_schema)
            self.transactions = TransactionRepository(db_manager_with_schema)
            self.data_imports = DataImportRepository(db_manager_with_schema)
            self.categories = CategoryRepository(db_manager_with_schema)
            self.budgets = BudgetRepository(db_manager_with_schema)

    return _TestServices()
