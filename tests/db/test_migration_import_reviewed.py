"""Tests for migration 012 (transactions.import_reviewed) backfill + schema."""

import sqlite3

import pytest

from config import get_migrations_dir


def _apply_range(conn, lo, hi):
    """Apply sorted migrations whose numeric prefix is in [lo, hi]."""
    for path in sorted(get_migrations_dir().glob("*.sql")):
        number = int(path.name.split("_", 1)[0])
        if lo <= number <= hi:
            with open(path) as f:
                conn.executescript(f.read())
    conn.commit()


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()


def _seed_pre_012_transaction(conn):
    conn.execute(
        "INSERT INTO accounts (name, account_type, description) VALUES ('a', 'bofa', 'A')"
    )
    conn.execute("INSERT INTO data_imports (account_id, filename) VALUES (1, NULL)")
    conn.execute(
        """
        INSERT INTO transactions
            (id, account_id, data_import_id, transaction_date, description,
             amount, transaction_type)
        VALUES ('abc', 1, 1, '2024-01-15', 'Old txn', 500, 'expense')
        """
    )
    conn.commit()


def test_existing_rows_backfilled_to_reviewed(conn):
    _apply_range(conn, 1, 11)
    _seed_pre_012_transaction(conn)

    _apply_range(conn, 12, 12)

    row = conn.execute(
        "SELECT import_reviewed FROM transactions WHERE id = 'abc'"
    ).fetchone()
    assert row[0] == 1  # pre-existing transactions are treated as reviewed


def test_new_rows_default_unreviewed(conn):
    _apply_range(conn, 1, 12)
    conn.execute(
        "INSERT INTO accounts (name, account_type, description) VALUES ('a', 'bofa', 'A')"
    )
    conn.execute("INSERT INTO data_imports (account_id, filename) VALUES (1, NULL)")
    conn.execute(
        """
        INSERT INTO transactions
            (id, account_id, data_import_id, transaction_date, description,
             amount, transaction_type)
        VALUES ('new', 1, 1, '2024-02-01', 'New txn', 700, 'expense')
        """
    )
    conn.commit()

    row = conn.execute(
        "SELECT import_reviewed FROM transactions WHERE id = 'new'"
    ).fetchone()
    assert row[0] == 0  # NOT NULL DEFAULT 0


def test_import_reviewed_is_not_null(conn):
    _apply_range(conn, 1, 12)
    cols = {r[1]: r for r in conn.execute("PRAGMA table_info(transactions)").fetchall()}
    assert "import_reviewed" in cols
    # PRAGMA table_info: index 3 is "notnull", index 4 is dflt_value.
    assert cols["import_reviewed"][3] == 1
    assert cols["import_reviewed"][4] == "0"
