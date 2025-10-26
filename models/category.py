"""Category model for transaction categorization."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Category:
    """Represents a user-defined transaction category.

    Attributes:
        id: Unique identifier (auto-generated).
        name: Category name (unique).
        description: Optional description of what belongs in this category.
    """

    id: int
    name: str
    description: Optional[str]
