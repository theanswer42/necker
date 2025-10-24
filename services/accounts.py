"""Account service for database operations."""

from typing import List, Optional
from db import manager as dbmgr
from models.account import Account


def find_all() -> List[Account]:
    """Get all accounts from the database.

    Returns:
        List of Account objects, ordered by id.
    """
    with dbmgr.connect() as conn:
        cursor = conn.execute(
            "SELECT id, name, type, description FROM accounts ORDER BY id"
        )
        rows = cursor.fetchall()

        return [
            Account(id=row[0], name=row[1], type=row[2], description=row[3])
            for row in rows
        ]


def find(account_id: int) -> Optional[Account]:
    """Get a single account by ID.

    Args:
        account_id: The account ID to find.

    Returns:
        Account object if found, None otherwise.
    """
    with dbmgr.connect() as conn:
        cursor = conn.execute(
            "SELECT id, name, type, description FROM accounts WHERE id = ?",
            (account_id,),
        )
        row = cursor.fetchone()

        if row:
            return Account(id=row[0], name=row[1], type=row[2], description=row[3])
        return None


def find_by_name(name: str) -> Optional[Account]:
    """Get a single account by name.

    Args:
        name: The account name to find.

    Returns:
        Account object if found, None otherwise.
    """
    with dbmgr.connect() as conn:
        cursor = conn.execute(
            "SELECT id, name, type, description FROM accounts WHERE name = ?", (name,)
        )
        row = cursor.fetchone()

        if row:
            return Account(id=row[0], name=row[1], type=row[2], description=row[3])
        return None


def create(name: str, account_type: str, description: str) -> Account:
    """Create a new account.

    Args:
        name: Account name (should be unique).
        account_type: Ingestion module name (e.g., "bofa").
        description: Human-readable description.

    Returns:
        The created Account object with id populated.

    Raises:
        Exception: If account creation fails (e.g., duplicate name).
    """
    with dbmgr.connect() as conn:
        cursor = conn.execute(
            "INSERT INTO accounts (name, type, description) VALUES (?, ?, ?)",
            (name, account_type, description),
        )
        conn.commit()
        account_id = cursor.lastrowid

        return Account(
            id=account_id, name=name, type=account_type, description=description
        )


def delete(account_id: int) -> bool:
    """Delete an account by ID.

    Args:
        account_id: The account ID to delete.

    Returns:
        True if account was deleted, False if not found.
    """
    with dbmgr.connect() as conn:
        cursor = conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        conn.commit()
        return cursor.rowcount > 0
