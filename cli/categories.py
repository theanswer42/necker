#!/usr/bin/env python3

import sys
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

    # Create category via service
    try:
        category = services.categories.create(name, description)

        logger.info(f"\n✓ Category created successfully with ID: {category.id}")
        logger.info(f"  Name: {category.name}")
        if category.description:
            logger.info(f"  Description: {category.description}")

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
