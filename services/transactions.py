"""Transaction service for database operations."""

import json
from typing import List, Optional
from datetime import date
from decimal import Decimal
from models.transaction import Transaction


class TransactionService:
    """Service for managing transactions."""

    def __init__(self, db_manager):
        """Initialize the transaction service.

        Args:
            db_manager: Database manager instance for database operations.
        """
        self.db_manager = db_manager

    def create(self, transaction: Transaction) -> Transaction:
        """Create a single transaction in the database.

        Args:
            transaction: Transaction object to insert.

        Returns:
            The same Transaction object (already has its ID from checksum).

        Raises:
            Exception: If transaction creation fails (e.g., duplicate ID, invalid account).
        """
        with self.db_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO transactions (
                    id, account_id, data_import_id, transaction_date, post_date,
                    description, category, amount, transaction_type,
                    additional_metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction.id,
                    transaction.account_id,
                    transaction.data_import_id,
                    transaction.transaction_date.isoformat(),
                    (
                        transaction.post_date.isoformat()
                        if transaction.post_date
                        else None
                    ),
                    transaction.description,
                    transaction.category,
                    float(transaction.amount),
                    transaction.type,
                    (
                        json.dumps(transaction.additional_metadata)
                        if transaction.additional_metadata
                        else None
                    ),
                ),
            )
            conn.commit()

        return transaction

    def bulk_create(self, transactions: List[Transaction]) -> int:
        """Create multiple transactions in the database in a single transaction.

        Args:
            transactions: List of Transaction objects to insert.

        Returns:
            Number of transactions successfully inserted.

        Raises:
            Exception: If bulk insert fails. All inserts are rolled back on error.
        """
        if not transactions:
            return 0

        with self.db_manager.connect() as conn:
            # Prepare all transaction data
            data = [
                (
                    t.id,
                    t.account_id,
                    t.data_import_id,
                    t.transaction_date.isoformat(),
                    t.post_date.isoformat() if t.post_date else None,
                    t.description,
                    t.category,
                    float(t.amount),
                    t.type,
                    json.dumps(t.additional_metadata)
                    if t.additional_metadata
                    else None,
                )
                for t in transactions
            ]

            # Execute bulk insert
            conn.executemany(
                """
                INSERT OR IGNORE INTO transactions (
                    id, account_id, data_import_id, transaction_date, post_date,
                    description, category, amount, transaction_type,
                    additional_metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                data,
            )
            conn.commit()

            # Return count of inserted rows
            return conn.total_changes

    def find_by_account(self, account_id: int) -> List[Transaction]:
        """Get all transactions for a specific account.

        Args:
            account_id: The account ID to filter by.

        Returns:
            List of Transaction objects ordered by transaction_date (newest first).
        """
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                """
                SELECT id, account_id, data_import_id, transaction_date, post_date,
                       description, category, amount, transaction_type,
                       additional_metadata
                FROM transactions
                WHERE account_id = ?
                ORDER BY transaction_date DESC, id
                """,
                (account_id,),
            )
            rows = cursor.fetchall()

            return [self._row_to_transaction(row) for row in rows]

    def find(self, transaction_id: str) -> Optional[Transaction]:
        """Get a single transaction by ID.

        Args:
            transaction_id: The transaction checksum ID.

        Returns:
            Transaction object if found, None otherwise.
        """
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                """
                SELECT id, account_id, data_import_id, transaction_date, post_date,
                       description, category, amount, transaction_type,
                       additional_metadata
                FROM transactions
                WHERE id = ?
                """,
                (transaction_id,),
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_transaction(row)
            return None

    def _row_to_transaction(self, row: tuple) -> Transaction:
        """Convert a database row to a Transaction object."""
        return Transaction(
            id=row[0],
            account_id=row[1],
            transaction_date=date.fromisoformat(row[3]),
            post_date=date.fromisoformat(row[4]) if row[4] else None,
            description=row[5],
            category=row[6],
            amount=Decimal(str(row[7])),
            type=row[8],
            additional_metadata=json.loads(row[9]) if row[9] else None,
            data_import_id=row[2],
        )
