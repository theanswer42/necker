"""Database manager for SQLite connections and path management."""

import sqlite3
from contextlib import contextmanager
from config import Config, get_migrations_dir


class DatabaseManager:
    """Manages database connections and paths.

    Args:
        config: Application configuration object.
    """

    def __init__(self, config: Config):
        """Initialize the database manager.

        Args:
            config: Config object containing database configuration.
        """
        self.config = config

    @contextmanager
    def connect(self):
        """Get a database connection with automatic cleanup.

        Yields:
            sqlite3.Connection: Database connection.
        """
        db_path = self.config.db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    def get_db_path(self):
        """Get the current database path.

        Returns:
            Path: Path to the database file.
        """
        return self.config.db_path

    def get_migrations_dir(self):
        """Get the migrations directory path.

        Returns:
            Path: Path to the migrations directory.
        """
        return get_migrations_dir()
