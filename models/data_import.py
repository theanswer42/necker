"""DataImport model representing a CSV import operation."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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
    filename: Optional[str]
    created_at: datetime
