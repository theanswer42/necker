"""DataImport model representing a CSV import operation."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class DataImport:
    """Represents a data import operation.

    Attributes:
        id: Unique identifier (auto-generated).
        account_id: ID of the account this import belongs to.
        filename: Name of the archived file (None if archiving disabled).
        created_at: Timestamp when the import was created.
    """

    id: int
    account_id: int
    filename: str | None
    created_at: datetime
