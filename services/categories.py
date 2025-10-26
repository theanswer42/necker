"""Category service for database operations."""

from typing import List, Optional
from models.category import Category


class CategoryService:
    """Service for managing categories."""

    def __init__(self, db_manager):
        """Initialize the category service.

        Args:
            db_manager: Database manager instance for database operations.
        """
        self.db_manager = db_manager

    def find_all(self) -> List[Category]:
        """Get all categories from the database.

        Returns:
            List of Category objects, ordered by name.
        """
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                "SELECT id, name, description FROM categories ORDER BY name"
            )
            rows = cursor.fetchall()

            return [
                Category(id=row[0], name=row[1], description=row[2]) for row in rows
            ]

    def find(self, category_id: int) -> Optional[Category]:
        """Get a single category by ID.

        Args:
            category_id: The category ID to find.

        Returns:
            Category object if found, None otherwise.
        """
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                "SELECT id, name, description FROM categories WHERE id = ?",
                (category_id,),
            )
            row = cursor.fetchone()

            if row:
                return Category(id=row[0], name=row[1], description=row[2])
            return None

    def find_by_name(self, name: str) -> Optional[Category]:
        """Get a single category by name.

        Args:
            name: The category name to find.

        Returns:
            Category object if found, None otherwise.
        """
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                "SELECT id, name, description FROM categories WHERE name = ?",
                (name,),
            )
            row = cursor.fetchone()

            if row:
                return Category(id=row[0], name=row[1], description=row[2])
            return None

    def create(self, name: str, description: Optional[str] = None) -> Category:
        """Create a new category.

        Args:
            name: Category name (should be unique).
            description: Optional description of the category.

        Returns:
            The created Category object with id populated.

        Raises:
            Exception: If category creation fails (e.g., duplicate name).
        """
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO categories (name, description) VALUES (?, ?)",
                (name, description),
            )
            conn.commit()
            category_id = cursor.lastrowid

            return Category(id=category_id, name=name, description=description)

    def update(
        self, category_id: int, name: str, description: Optional[str] = None
    ) -> Category:
        """Update an existing category.

        Args:
            category_id: The category ID to update.
            name: New category name.
            description: New description (can be None).

        Returns:
            The updated Category object.

        Raises:
            Exception: If category not found or update fails.
        """
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                "UPDATE categories SET name = ?, description = ? WHERE id = ?",
                (name, description, category_id),
            )
            conn.commit()

            if cursor.rowcount == 0:
                raise Exception(f"Category with ID {category_id} not found")

            return Category(id=category_id, name=name, description=description)

    def delete(self, category_id: int) -> bool:
        """Delete a category by ID.

        Args:
            category_id: The category ID to delete.

        Returns:
            True if category was deleted, False if not found.
        """
        with self.db_manager.connect() as conn:
            cursor = conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            conn.commit()
            return cursor.rowcount > 0
