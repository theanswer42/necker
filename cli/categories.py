#!/usr/bin/env python3

import sys
import json
from pathlib import Path
from logger import get_logger

logger = get_logger()


def cmd_list(args, services):
    """List all categories in the database."""
    categories = services.categories.find_all()

    if not categories:
        logger.info("No categories found.")
        return

    logger.info("\nCategories:")
    logger.info("=" * 80)
    for category in categories:
        logger.info(f"ID: {category.id}")
        logger.info(f"Name: {category.name}")
        if category.description:
            logger.info(f"Description: {category.description}")
        if category.parent_id:
            parent = services.categories.find(category.parent_id)
            parent_name = parent.name if parent else "Unknown"
            logger.info(f"Parent: {parent_name} (ID: {category.parent_id})")
        logger.info("-" * 80)

    logger.info(f"\nTotal categories: {len(categories)}")


def cmd_create(args, services):
    """Interactively create a new category."""
    print("\nCreate New Category")
    print("=" * 80)

    # Get category name
    name = input("Category name (e.g., Groceries): ").strip()
    if not name:
        logger.error("Category name cannot be empty.")
        sys.exit(1)

    # Get description
    description = input("Description (optional, press Enter to skip): ").strip()
    if not description:
        description = None

    # Get parent category
    parent_id = None
    parent_input = input("Parent category ID (optional, press Enter to skip): ").strip()
    if parent_input:
        try:
            parent_id = int(parent_input)
            # Verify parent exists
            parent = services.categories.find(parent_id)
            if not parent:
                logger.error(f"Parent category with ID {parent_id} not found.")
                sys.exit(1)
        except ValueError:
            logger.error("Parent category ID must be a number.")
            sys.exit(1)

    # Create category via service
    try:
        category = services.categories.create(name, description, parent_id)

        logger.info(f"\n✓ Category created successfully with ID: {category.id}")
        logger.info(f"  Name: {category.name}")
        if category.description:
            logger.info(f"  Description: {category.description}")
        if category.parent_id:
            logger.info(f"  Parent ID: {category.parent_id}")

    except Exception as e:
        logger.error(f"Error creating category: {e}")
        sys.exit(1)


def cmd_delete(args, services):
    """Delete a category by ID."""
    category_id = args.category_id

    # Check if category exists
    category = services.categories.find(category_id)
    if not category:
        logger.error(f"Category with ID {category_id} not found.")
        sys.exit(1)

    # Confirm deletion
    logger.info("\nCategory to delete:")
    logger.info(f"  ID: {category.id}")
    logger.info(f"  Name: {category.name}")
    if category.description:
        logger.info(f"  Description: {category.description}")

    confirm = (
        input("\nAre you sure you want to delete this category? (yes/no): ")
        .strip()
        .lower()
    )
    if confirm != "yes":
        logger.info("Deletion cancelled.")
        return

    # Delete category
    try:
        if services.categories.delete(category_id):
            logger.info(f"✓ Category '{category.name}' deleted successfully.")
        else:
            logger.error("Failed to delete category.")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error deleting category: {e}")
        sys.exit(1)


def cmd_seed(args, services):
    """Seed categories from JSON file."""
    # Get path to seed file
    seed_file = Path(__file__).parent.parent / "db" / "seed" / "categories.json"

    if not seed_file.exists():
        logger.error(f"Seed file not found: {seed_file}")
        sys.exit(1)

    # Load categories from JSON
    try:
        with open(seed_file, "r") as f:
            categories_data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error reading seed file: {e}")
        sys.exit(1)

    logger.info("\nSeeding categories from db/seed/categories.json")
    logger.info("=" * 80)

    created_count = 0
    skipped_count = 0

    # Process each top-level category
    for category_data in categories_data:
        name = category_data.get("name")
        description = category_data.get("description")
        children = category_data.get("children", [])

        if not name:
            logger.warning("Skipping category with no name")
            continue

        # Check if parent category exists
        existing = services.categories.find_by_name(name)
        if existing:
            logger.info(f"⊘ Skipped '{name}' (already exists)")
            skipped_count += 1
            parent_id = existing.id
        else:
            # Create parent category
            try:
                parent = services.categories.create(name, description)
                logger.info(f"✓ Created '{name}' (ID: {parent.id})")
                created_count += 1
                parent_id = parent.id
            except Exception as e:
                logger.error(f"Error creating category '{name}': {e}")
                continue

        # Process child categories
        for child_data in children:
            child_name = child_data.get("name")
            child_description = child_data.get("description")

            if not child_name:
                logger.warning(f"Skipping child of '{name}' with no name")
                continue

            # Prefix child name with parent name
            prefixed_child_name = f"{name}/{child_name}"

            # Check if child category exists
            existing_child = services.categories.find_by_name(prefixed_child_name)
            if existing_child:
                logger.info(f"  ⊘ Skipped '{prefixed_child_name}' (already exists)")
                skipped_count += 1
            else:
                # Create child category
                try:
                    child = services.categories.create(
                        prefixed_child_name, child_description, parent_id
                    )
                    logger.info(f"  ✓ Created '{prefixed_child_name}' (ID: {child.id})")
                    created_count += 1
                except Exception as e:
                    logger.error(
                        f"Error creating category '{prefixed_child_name}': {e}"
                    )
                    continue

    logger.info("=" * 80)
    logger.info("\nSeeding complete!")
    logger.info(f"Created: {created_count}")
    logger.info(f"Skipped: {skipped_count}")
    logger.info(f"Total: {created_count + skipped_count}")


def setup_parser(subparsers):
    """Setup categories subcommand parser.

    Args:
        subparsers: The subparsers object from the main CLI
    """
    parser = subparsers.add_parser(
        "categories",
        help="Manage categories",
        description="Create, list, and delete transaction categories",
    )

    # Add subcommands for categories
    categories_subparsers = parser.add_subparsers(
        title="subcommands",
        description="Available category commands",
        dest="subcommand",
        required=True,
    )

    # categories list
    list_parser = categories_subparsers.add_parser("list", help="List all categories")
    list_parser.set_defaults(func=cmd_list)

    # categories create
    create_parser = categories_subparsers.add_parser(
        "create", help="Create a new category interactively"
    )
    create_parser.set_defaults(func=cmd_create)

    # categories delete
    delete_parser = categories_subparsers.add_parser(
        "delete", help="Delete a category by ID"
    )
    delete_parser.add_argument(
        "category_id",
        type=int,
        help="ID of the category to delete",
    )
    delete_parser.set_defaults(func=cmd_delete)

    # categories seed
    seed_parser = categories_subparsers.add_parser(
        "seed", help="Seed categories from JSON file"
    )
    seed_parser.set_defaults(func=cmd_seed)
