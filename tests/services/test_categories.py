import pytest
import sqlite3


class TestCategoryService:
    """Tests for CategoryService."""

    def test_create_category_simple(self, services):
        """Test creating a simple category without parent."""
        category = services.categories.create("Groceries", "Food and groceries")

        assert category.id is not None
        assert category.id > 0
        assert category.name == "Groceries"
        assert category.description == "Food and groceries"
        assert category.parent_id is None

    def test_create_category_with_parent(self, services):
        """Test creating a category with a parent."""
        parent = services.categories.create("Food", "All food categories")
        child = services.categories.create(
            "Groceries", "Food and groceries", parent_id=parent.id
        )

        assert child.parent_id == parent.id

    def test_create_category_without_description(self, services):
        """Test creating a category without a description."""
        category = services.categories.create("Utilities")

        assert category.name == "Utilities"
        assert category.description is None

    def test_find_category_by_id(self, services):
        """Test finding a category by ID."""
        created = services.categories.create("Transport", "Transportation costs")

        found = services.categories.find(created.id)

        assert found is not None
        assert found.id == created.id
        assert found.name == "Transport"
        assert found.description == "Transportation costs"

    def test_find_category_by_id_not_found(self, services):
        """Test finding a non-existent category returns None."""
        found = services.categories.find(9999)

        assert found is None

    def test_find_by_name(self, services):
        """Test finding a category by name."""
        services.categories.create("Entertainment", "Movies, games, etc.")

        found = services.categories.find_by_name("Entertainment")

        assert found is not None
        assert found.name == "Entertainment"
        assert found.description == "Movies, games, etc."

    def test_find_by_name_not_found(self, services):
        """Test finding a non-existent category by name returns None."""
        found = services.categories.find_by_name("Nonexistent")

        assert found is None

    def test_find_by_name_case_sensitive(self, services):
        """Test that category name lookup is case-sensitive."""
        services.categories.create("Shopping", "Shopping expenses")

        found = services.categories.find_by_name("shopping")

        assert found is None

    def test_find_all_empty(self, services):
        """Test finding all categories when database is empty."""
        categories = services.categories.find_all()

        assert categories == []
        assert isinstance(categories, list)

    def test_find_all_single_category(self, services):
        """Test finding all categories with one category."""
        created = services.categories.create("Single", "Single category")

        categories = services.categories.find_all()

        assert len(categories) == 1
        assert categories[0].id == created.id

    def test_find_all_multiple_categories(self, services):
        """Test finding all categories with multiple categories."""
        services.categories.create("Zebra", "Last alphabetically")
        services.categories.create("Alpha", "First alphabetically")
        services.categories.create("Beta", "Second alphabetically")

        categories = services.categories.find_all()

        assert len(categories) == 3
        # Should be ordered by name
        assert categories[0].name == "Alpha"
        assert categories[1].name == "Beta"
        assert categories[2].name == "Zebra"

    def test_create_duplicate_name_raises_error(self, services):
        """Test that creating a category with duplicate name raises an error."""
        services.categories.create("Duplicate", "First")

        with pytest.raises(sqlite3.IntegrityError):
            services.categories.create("Duplicate", "Second")

    def test_update_category_name(self, services):
        """Test updating a category's name."""
        category = services.categories.create("OldName", "Description")

        updated = services.categories.update(category.id, "NewName", "Description")

        assert updated.id == category.id
        assert updated.name == "NewName"
        assert updated.description == "Description"

        # Verify in database
        found = services.categories.find(category.id)
        assert found.name == "NewName"

    def test_update_category_description(self, services):
        """Test updating a category's description."""
        category = services.categories.create("Name", "Old description")

        updated = services.categories.update(category.id, "Name", "New description")

        assert updated.description == "New description"

        found = services.categories.find(category.id)
        assert found.description == "New description"

    def test_update_category_parent_id(self, services):
        """Test updating a category's parent_id."""
        parent = services.categories.create("Parent", "Parent category")
        child = services.categories.create("Child", "Child category")

        # Set parent
        updated = services.categories.update(
            child.id, "Child", "Child category", parent_id=parent.id
        )

        assert updated.parent_id == parent.id

        found = services.categories.find(child.id)
        assert found.parent_id == parent.id

    def test_update_category_remove_parent(self, services):
        """Test removing a category's parent by setting parent_id to None."""
        parent = services.categories.create("Parent", "Parent category")
        child = services.categories.create(
            "Child", "Child category", parent_id=parent.id
        )

        # Remove parent
        updated = services.categories.update(
            child.id, "Child", "Child category", parent_id=None
        )

        assert updated.parent_id is None

        found = services.categories.find(child.id)
        assert found.parent_id is None

    def test_update_nonexistent_category_raises_error(self, services):
        """Test that updating a non-existent category raises an error."""
        with pytest.raises(Exception, match="Category with ID 9999 not found"):
            services.categories.update(9999, "Name", "Description")

    def test_delete_category(self, services):
        """Test deleting a category."""
        category = services.categories.create("ToDelete", "Will be deleted")

        result = services.categories.delete(category.id)

        assert result is True

        # Verify it's gone
        found = services.categories.find(category.id)
        assert found is None

    def test_delete_nonexistent_category(self, services):
        """Test deleting a non-existent category returns False."""
        result = services.categories.delete(9999)

        assert result is False

    def test_delete_does_not_affect_other_categories(self, services):
        """Test that deleting one category doesn't affect others."""
        services.categories.create("Keep1", "Keep this")
        cat2 = services.categories.create("Delete", "Delete this")
        services.categories.create("Keep2", "Keep this too")

        services.categories.delete(cat2.id)

        remaining = services.categories.find_all()
        assert len(remaining) == 2
        names = {cat.name for cat in remaining}
        assert names == {"Keep1", "Keep2"}

    def test_hierarchical_categories_three_levels(self, services):
        """Test creating a three-level category hierarchy."""
        level1 = services.categories.create("Expenses", "All expenses")
        level2 = services.categories.create(
            "Food", "Food expenses", parent_id=level1.id
        )
        level3 = services.categories.create(
            "Restaurants", "Restaurant expenses", parent_id=level2.id
        )

        # Verify relationships
        assert level2.parent_id == level1.id
        assert level3.parent_id == level2.id

        # Verify all can be found
        found1 = services.categories.find(level1.id)
        found2 = services.categories.find(level2.id)
        found3 = services.categories.find(level3.id)

        assert found1.parent_id is None
        assert found2.parent_id == level1.id
        assert found3.parent_id == level2.id

    def test_find_all_includes_parent_id(self, services):
        """Test that find_all correctly returns parent_id for hierarchical categories."""
        parent = services.categories.create("Parent", "Parent")
        services.categories.create("Child1", "Child 1", parent_id=parent.id)
        services.categories.create("Child2", "Child 2", parent_id=parent.id)

        categories = services.categories.find_all()

        # Find the children
        children = [c for c in categories if c.parent_id == parent.id]
        assert len(children) == 2

    def test_create_category_with_special_characters(self, services):
        """Test creating category with special characters."""
        category = services.categories.create("Food & Drink", "Food, drinks, & dining")

        found = services.categories.find(category.id)
        assert found.name == "Food & Drink"
        assert found.description == "Food, drinks, & dining"

    def test_create_category_with_empty_string_description(self, services):
        """Test creating category with empty string description."""
        category = services.categories.create("Test", "")

        found = services.categories.find(category.id)
        assert found.description == ""

    def test_update_all_fields_at_once(self, services):
        """Test updating all fields of a category at once."""
        parent1 = services.categories.create("Parent1", "First parent")
        parent2 = services.categories.create("Parent2", "Second parent")
        category = services.categories.create(
            "OldName", "Old description", parent_id=parent1.id
        )

        updated = services.categories.update(
            category.id, "NewName", "New description", parent_id=parent2.id
        )

        assert updated.name == "NewName"
        assert updated.description == "New description"
        assert updated.parent_id == parent2.id

        found = services.categories.find(category.id)
        assert found.name == "NewName"
        assert found.description == "New description"
        assert found.parent_id == parent2.id

    def test_multiple_children_same_parent(self, services):
        """Test that multiple categories can have the same parent."""
        parent = services.categories.create("Shopping", "All shopping")
        services.categories.create("Clothes", "Clothing", parent_id=parent.id)
        services.categories.create("Electronics", "Electronics", parent_id=parent.id)
        services.categories.create("Books", "Books", parent_id=parent.id)

        # Verify all have the same parent
        categories = services.categories.find_all()
        children = [c for c in categories if c.parent_id == parent.id]

        assert len(children) == 3
        child_names = {c.name for c in children}
        assert child_names == {"Clothes", "Electronics", "Books"}
