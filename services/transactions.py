"""Transaction service for database operations."""

import json
from typing import List, Optional
from datetime import date, timedelta
from decimal import Decimal
from models.transaction import Transaction

# SQL Query Constants
_TRANSACTION_SELECT_FIELDS = """id, account_id, data_import_id, transaction_date, post_date,
       description, bank_category, category_id, auto_category_id, amount, transaction_type,
       additional_metadata, amortize_months, amortize_end_date"""

_TRANSACTION_INSERT_FIELDS = """id, account_id, data_import_id, transaction_date, post_date,
    description, bank_category, category_id, auto_category_id, amount, transaction_type,
    additional_metadata, amortize_months, amortize_end_date"""

# Automatically generate placeholders from field count
_TRANSACTION_INSERT_PLACEHOLDERS = (
    f"({', '.join(['?'] * len(_TRANSACTION_INSERT_FIELDS.split(',')))})"
)


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
                f"""
                INSERT INTO transactions ({_TRANSACTION_INSERT_FIELDS})
                VALUES {_TRANSACTION_INSERT_PLACEHOLDERS}
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
                    transaction.amortize_months,
                    (
                        transaction.amortize_end_date.isoformat()
                        if transaction.amortize_end_date
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
                    t.amortize_months,
                    t.amortize_end_date.isoformat() if t.amortize_end_date else None,
                )
                for t in transactions
            ]

            # Execute bulk insert
            conn.executemany(
                f"""
                INSERT OR IGNORE INTO transactions ({_TRANSACTION_INSERT_FIELDS})
                VALUES {_TRANSACTION_INSERT_PLACEHOLDERS}
                """,
                data,
            )
            conn.commit()

            # Return count of inserted rows
            return conn.total_changes

    def batch_update(
        self, transactions: List[Transaction], field_names: List[str]
    ) -> int:
        """Update specified fields for multiple transactions.

        Args:
            transactions: List of Transaction objects to update.
            field_names: List of field names to update. Supported fields:
                        'category_id', 'auto_category_id', 'amortize_months', 'amortize_end_date'

        Returns:
            Number of transactions successfully updated.

        Raises:
            ValueError: If unsupported field names are provided.
            Exception: If batch update fails. All updates are rolled back on error.
        """
        if not transactions:
            return 0

        if not field_names:
            raise ValueError("field_names cannot be empty")

        # Validate field names
        supported_fields = {
            "category_id",
            "auto_category_id",
            "amortize_months",
            "amortize_end_date",
        }
        invalid_fields = set(field_names) - supported_fields
        if invalid_fields:
            raise ValueError(f"Unsupported field names: {invalid_fields}")

        # Build SET clause dynamically
        set_clause = ", ".join([f"{field} = ?" for field in field_names])

        with self.db_manager.connect() as conn:
            # Prepare update data - field values followed by transaction ID
            data = []
            for t in transactions:
                row_data = []
                for field in field_names:
                    value = getattr(t, field)
                    # Handle date serialization
                    if field == "amortize_end_date" and value is not None:
                        value = value.isoformat()
                    row_data.append(value)
                # Add transaction ID at the end for WHERE clause
                row_data.append(t.id)
                data.append(tuple(row_data))

            # Execute batch update
            cursor = conn.executemany(
                f"""
                UPDATE transactions
                SET {set_clause}
                WHERE id = ?
                """,
                data,
            )
            conn.commit()

            # Return count of updated rows
            return cursor.rowcount

    def update(self, transaction: Transaction, field_names: List[str]) -> bool:
        """Update specified fields for a single transaction.

        Args:
            transaction: Transaction object to update.
            field_names: List of field names to update. Supported fields:
                        'category_id', 'auto_category_id', 'amortize_months', 'amortize_end_date'

        Returns:
            True if update was successful, False otherwise.

        Raises:
            ValueError: If unsupported field names are provided.
            Exception: If update fails.
        """
        count = self.batch_update([transaction], field_names)
        return count > 0

    def find_by_account(self, account_id: int) -> List[Transaction]:
        """Get all transactions for a specific account.

        Args:
            account_id: The account ID to filter by.

        Returns:
            List of Transaction objects ordered by transaction_date (newest first).
        """
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                f"""
                SELECT {_TRANSACTION_SELECT_FIELDS}
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
                f"""
                SELECT {_TRANSACTION_SELECT_FIELDS}
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
                f"""
                SELECT {_TRANSACTION_SELECT_FIELDS}
                FROM transactions
                WHERE id = ?
                """,
                (transaction_id,),
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_transaction(row)
            return None

    def get_transactions_by_date_range(
        self,
        start_date: str,
        end_date: str,
        *,
        account_id: Optional[int] = None,
        exclude_amortized: bool = False,
        category_ids: Optional[List[int]] = None,
    ) -> List[Transaction]:
        """Get transactions within a date range.

        Args:
            start_date: Start date in ISO format (YYYY-MM-DD).
            end_date: End date in ISO format (YYYY-MM-DD).
            account_id: Optional account ID to filter by.
            exclude_amortized: If True, exclude transactions with amortize_months set.
            category_ids: Optional list of category IDs to filter by.

        Returns:
            List of Transaction objects ordered by date (newest first).
        """
        query = f"""
            SELECT {_TRANSACTION_SELECT_FIELDS}
            FROM transactions
            WHERE transaction_date >= ? AND transaction_date <= ?
        """

        params = [start_date, end_date]

        if account_id is not None:
            query += " AND account_id = ?"
            params.append(account_id)

        if exclude_amortized:
            query += " AND amortize_months IS NULL"

        if category_ids is not None and len(category_ids) > 0:
            placeholders = ", ".join(["?"] * len(category_ids))
            query += f" AND category_id IN ({placeholders})"
            params.extend(category_ids)

        query += " ORDER BY transaction_date DESC, id"

        with self.db_manager.connect() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_transaction(row) for row in rows]

    def get_transactions_by_month(
        self,
        year: int,
        month: int,
        *,
        account_id: Optional[int] = None,
        exclude_amortized: bool = False,
        category_ids: Optional[List[int]] = None,
    ) -> List[Transaction]:
        """Get transactions for a specific month.

        Args:
            year: Year (e.g., 2025).
            month: Month (1-12).
            account_id: Optional account ID to filter by.
            exclude_amortized: If True, exclude transactions with amortize_months set.
            category_ids: Optional list of category IDs to filter by.

        Returns:
            List of Transaction objects ordered by date (newest first).
        """
        import calendar

        # Calculate start and end dates for the month
        start_date = f"{year:04d}-{month:02d}-01"

        # Get last day of month
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year:04d}-{month:02d}-{last_day:02d}"

        return self.get_transactions_by_date_range(
            start_date,
            end_date,
            account_id=account_id,
            exclude_amortized=exclude_amortized,
            category_ids=category_ids,
        )

    def get_accrued_transactions_by_month(
        self,
        year: int,
        month: int,
        *,
        account_id: Optional[int] = None,
        category_ids: Optional[List[int]] = None,
    ) -> List[Transaction]:
        """Get accrued transactions for a specific month.

        Returns virtual Transaction objects representing the monthly accrual
        for transactions that have amortization set. These are not stored in
        the database and have the 'accrued' flag set to True.

        Args:
            year: Year (e.g., 2025).
            month: Month (1-12).
            account_id: Optional account ID to filter by.
            category_ids: Optional list of category IDs to filter by.

        Returns:
            List of virtual Transaction objects with accrued amounts and dates.
            Each transaction has:
            - transaction_date set to start of the target month
            - amount set to original_amount / amortize_months (rounded to 2 decimals)
            - accrued flag set to True
        """
        import calendar

        # Calculate start and end dates for the month
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)

        # Build query to find transactions that accrue in this month
        query = f"""
            SELECT {_TRANSACTION_SELECT_FIELDS}
            FROM transactions
            WHERE transaction_date <= ?
              AND amortize_end_date >= ?
              AND amortize_months IS NOT NULL
        """

        params = [end_date.isoformat(), start_date.isoformat()]

        if account_id is not None:
            query += " AND account_id = ?"
            params.append(account_id)

        if category_ids is not None and len(category_ids) > 0:
            placeholders = ", ".join(["?"] * len(category_ids))
            query += f" AND category_id IN ({placeholders})"
            params.extend(category_ids)

        query += " ORDER BY transaction_date DESC, id"

        with self.db_manager.connect() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            # Convert rows to Transaction objects and transform to accrued versions
            accrued_transactions = []
            for row in rows:
                original = self._row_to_transaction(row)

                # Calculate accrued amount (rounded to 2 decimals)
                accrued_amount = round(original.amount / original.amortize_months, 2)

                # Create new Transaction with accrued values
                accrued_txn = Transaction(
                    id=original.id,
                    account_id=original.account_id,
                    transaction_date=start_date,  # Set to start of target month
                    post_date=original.post_date,
                    description=original.description,
                    bank_category=original.bank_category,
                    amount=accrued_amount,
                    type=original.type,
                    additional_metadata=original.additional_metadata,
                    data_import_id=original.data_import_id,
                    category_id=original.category_id,
                    auto_category_id=original.auto_category_id,
                    amortize_months=original.amortize_months,
                    amortize_end_date=original.amortize_end_date,
                    accrued=True,  # Mark as accrued transaction
                )

                accrued_transactions.append(accrued_txn)

            return accrued_transactions

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
            amortize_months=row[12],
            amortize_end_date=date.fromisoformat(row[13]) if row[13] else None,
        )
