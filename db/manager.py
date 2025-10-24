import sqlite3
from contextlib import contextmanager
import config


@contextmanager
def connect():
    """Get a database connection with automatic cleanup."""
    db_path = config.get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_db_path():
    """Get the current database path."""
    return config.get_db_path()


def get_migrations_dir():
    """Get the migrations directory path."""
    return config.get_migrations_dir()
