"""DataImport service for database operations."""

from typing import List, Optional
from datetime import datetime
from models.data_import import DataImport


class DataImportService:
    """Service for managing data import records."""

    def __init__(self, db_manager):
        """Initialize the data import service.

        Args:
            db_manager: Database manager instance for database operations.
        """
        self.db_manager = db_manager

    def create(self, account_id: int, filename: Optional[str]) -> DataImport:
        """Create a new data import record.

        Args:
            account_id: ID of the account this import belongs to.
            filename: Name of the archived file (None if archiving disabled).

        Returns:
            The created DataImport object with id and created_at populated.

        Raises:
            Exception: If data import creation fails.
        """
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO data_imports (account_id, filename)
                VALUES (?, ?)
                """,
                (account_id, filename),
            )
            conn.commit()
            import_id = cursor.lastrowid

            # Fetch the created record to get the created_at timestamp
            cursor = conn.execute(
                "SELECT id, account_id, filename, created_at FROM data_imports WHERE id = ?",
                (import_id,),
            )
            row = cursor.fetchone()

            return self._row_to_data_import(row)

    def find(self, data_import_id: int) -> Optional[DataImport]:
        """Get a single data import by ID.

        Args:
            data_import_id: The data import ID to find.

        Returns:
            DataImport object if found, None otherwise.
        """
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                "SELECT id, account_id, filename, created_at FROM data_imports WHERE id = ?",
                (data_import_id,),
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_data_import(row)
            return None

    def find_by_account(self, account_id: int) -> List[DataImport]:
        """Get all data imports for a specific account.

        Args:
            account_id: The account ID to filter by.

        Returns:
            List of DataImport objects ordered by created_at (newest first).
        """
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                """
                SELECT id, account_id, filename, created_at
                FROM data_imports
                WHERE account_id = ?
                ORDER BY created_at DESC
                """,
                (account_id,),
            )
            rows = cursor.fetchall()

            return [self._row_to_data_import(row) for row in rows]

    def _row_to_data_import(self, row: tuple) -> DataImport:
        """Convert a database row to a DataImport object.

        Args:
            row: Database row tuple.

        Returns:
            DataImport object.
        """
        return DataImport(
            id=row[0],
            account_id=row[1],
            filename=row[2],
            created_at=datetime.fromisoformat(row[3]),
        )
