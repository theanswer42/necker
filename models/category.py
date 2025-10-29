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
        parent_id: Optional parent category ID for hierarchical categories.
    """

    id: int
    name: str
    description: Optional[str]
    parent_id: Optional[int] = None
