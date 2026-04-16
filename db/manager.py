"""Database manager for SQLite connections and path management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

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
        conn.execute("PRAGMA foreign_keys = ON")
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

    def backup_to(self, output_path: Path) -> None:
        """Back up the configured database to output_path using SQLite's online backup API.

        Raises:
            FileNotFoundError: If the source database or the output parent directory does not exist.
            FileExistsError: If output_path already exists.
        """
        db_path = self.config.db_path
        if not db_path.exists():
            raise FileNotFoundError(f"database does not exist: {db_path}")

        if not output_path.parent.exists():
            raise FileNotFoundError(
                f"output directory does not exist: {output_path.parent}"
            )

        if output_path.exists():
            raise FileExistsError(f"output path already exists: {output_path}")

        with self.connect() as source:
            dest = sqlite3.connect(output_path)
            try:
                source.backup(dest)
            finally:
                dest.close()
