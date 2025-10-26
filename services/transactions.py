"""Transaction service for database operations."""

import json
from typing import List, Optional
from datetime import date, timedelta
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
                    description, bank_category, category_id, auto_category_id, amount, transaction_type,
                    additional_metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    transaction.bank_category,
                    transaction.category_id,
                    transaction.auto_category_id,
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
                    t.bank_category,
                    t.category_id,
                    t.auto_category_id,
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
                    description, bank_category, category_id, auto_category_id, amount, transaction_type,
                    additional_metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                data,
            )
            conn.commit()

            # Return count of inserted rows
            return conn.total_changes

    def batch_update_auto_categories(self, transactions: List[Transaction]) -> int:
        """Update auto_category_id for multiple transactions.

        Args:
            transactions: List of Transaction objects with auto_category_id set.

        Returns:
            Number of transactions successfully updated.

        Raises:
            Exception: If batch update fails. All updates are rolled back on error.
        """
        if not transactions:
            return 0

        with self.db_manager.connect() as conn:
            # Prepare update data (auto_category_id, transaction_id)
            data = [(t.auto_category_id, t.id) for t in transactions]

            # Execute batch update
            conn.executemany(
                """
                UPDATE transactions
                SET auto_category_id = ?
                WHERE id = ?
                """,
                data,
            )
            conn.commit()

            # Return count of updated rows
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
                       description, bank_category, category_id, auto_category_id, amount, transaction_type,
                       additional_metadata
                FROM transactions
                WHERE account_id = ?
                ORDER BY transaction_date DESC, id
                """,
                (account_id,),
            )
            rows = cursor.fetchall()

            return [self._row_to_transaction(row) for row in rows]

    def find_historical_for_categorization(
        self, account_id: int, days: int = 90
    ) -> List[Transaction]:
        """Get historical categorized transactions for use in auto-categorization.

        Fetches transactions from the specified account that:
        - Are within the last N days
        - Have a manually-set category (category_id is not NULL)

        Args:
            account_id: The account ID to filter by.
            days: Number of days to look back (default 90).

        Returns:
            List of Transaction objects with manual categories, ordered by date (newest first).
        """
        cutoff_date = (date.today() - timedelta(days=days)).isoformat()

        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                """
                SELECT id, account_id, data_import_id, transaction_date, post_date,
                       description, bank_category, category_id, auto_category_id, amount, transaction_type,
                       additional_metadata
                FROM transactions
                WHERE account_id = ?
                  AND category_id IS NOT NULL
                  AND transaction_date >= ?
                ORDER BY transaction_date DESC, id
                """,
                (account_id, cutoff_date),
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
                       description, bank_category, category_id, auto_category_id, amount, transaction_type,
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
            bank_category=row[6],
            amount=Decimal(str(row[9])),
            type=row[10],
            additional_metadata=json.loads(row[11]) if row[11] else None,
            data_import_id=row[2],
            category_id=row[7],
            auto_category_id=row[8],
        )
