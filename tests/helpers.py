"""Helper utilities for tests."""

import sqlite3
from pathlib import Path


def run_migrations(conn: sqlite3.Connection, migrations_dir: Path) -> None:
    """Run all SQL migrations in order.

    Args:
        conn: SQLite connection to run migrations against.
        migrations_dir: Path to directory containing .sql migration files.
    """
    # Get all .sql files and sort them
    migration_files = sorted(migrations_dir.glob("*.sql"))

    for migration_file in migration_files:
        with open(migration_file, "r") as f:
            sql = f.read()

        # Execute the migration
        conn.executescript(sql)

    conn.commit()
