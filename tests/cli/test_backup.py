"""Tests for CLI backup command."""

import sqlite3
import pytest
from argparse import Namespace
from pathlib import Path

from config import Config, get_migrations_dir
from db.manager import DatabaseManager
from cli.backup import cmd_backup
from tests.helpers import run_migrations


def _make_config(tmp_path: Path) -> Config:
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


def _make_populated_db_manager(tmp_path: Path) -> DatabaseManager:
    """Create a DatabaseManager with a real file DB, migrations applied, one account inserted."""
    config = _make_config(tmp_path)
    db_manager = DatabaseManager(config)

    with db_manager.connect() as conn:
        run_migrations(conn, get_migrations_dir())
        conn.execute(
            "INSERT INTO accounts (name, account_type, description) VALUES (?, ?, ?)",
            ("acct", "bofa", "Test"),
        )
        conn.commit()

    return db_manager


def test_backup_creates_file_at_output_path(tmp_path):
    db_manager = _make_populated_db_manager(tmp_path)
    out = tmp_path / "backup.db"

    args = Namespace(output_path=str(out))
    cmd_backup(args, db_manager)

    assert out.exists()


def test_backup_contents_match_source(tmp_path):
    db_manager = _make_populated_db_manager(tmp_path)
    out = tmp_path / "backup.db"

    args = Namespace(output_path=str(out))
    cmd_backup(args, db_manager)

    # Open the backup as a plain sqlite DB and confirm our row survived.
    conn = sqlite3.connect(out)
    try:
        cursor = conn.execute("SELECT name, account_type FROM accounts")
        rows = cursor.fetchall()
    finally:
        conn.close()

    assert rows == [("acct", "bofa")]


def test_backup_schema_matches_source(tmp_path):
    db_manager = _make_populated_db_manager(tmp_path)
    out = tmp_path / "backup.db"

    args = Namespace(output_path=str(out))
    cmd_backup(args, db_manager)

    with db_manager.connect() as source:
        source_tables = {
            row[0]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    backup_conn = sqlite3.connect(out)
    try:
        backup_tables = {
            row[0]
            for row in backup_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        backup_conn.close()

    assert backup_tables == source_tables


def test_backup_errors_when_output_exists(tmp_path):
    db_manager = _make_populated_db_manager(tmp_path)
    out = tmp_path / "existing.db"
    out.write_bytes(b"not really a db")

    args = Namespace(output_path=str(out))
    with pytest.raises(FileExistsError):
        cmd_backup(args, db_manager)


def test_backup_errors_when_parent_missing(tmp_path):
    db_manager = _make_populated_db_manager(tmp_path)
    out = tmp_path / "nope" / "backup.db"

    args = Namespace(output_path=str(out))
    with pytest.raises(FileNotFoundError):
        cmd_backup(args, db_manager)


def test_backup_errors_when_source_db_missing(tmp_path):
    # Build a config whose db_path doesn't exist and never ran migrations.
    config = _make_config(tmp_path)
    db_manager = DatabaseManager(config)
    out = tmp_path / "backup.db"

    args = Namespace(output_path=str(out))
    with pytest.raises(FileNotFoundError):
        cmd_backup(args, db_manager)


def test_backup_refuses_to_overwrite_source(tmp_path):
    db_manager = _make_populated_db_manager(tmp_path)
    # Point output at the source db itself — caught by the "already exists" check.
    args = Namespace(output_path=str(db_manager.config.db_path))
    with pytest.raises(FileExistsError):
        cmd_backup(args, db_manager)
