#!/usr/bin/env python3

import sys
from logger import get_logger
from repositories.budgets import BudgetRepository
from repositories.categories import CategoryRepository

logger = get_logger()

VALID_PERIOD_TYPES = ("monthly", "yearly")


def _format_amount(cents: int) -> str:
    return f"${cents / 100:.2f}"


def cmd_list(args, db_manager, config):
    budgets = BudgetRepository(db_manager).find_all()

    if not budgets:
        logger.info("No budgets found.")
        return

    logger.info("\nBudgets:")
    logger.info("=" * 80)
    logger.info(f"{'ID':<6} {'Category':<30} {'Period':<10} {'Amount':<12}")
    logger.info("-" * 80)
    for b in budgets:
        logger.info(
            f"{b.id:<6} {b.category_name:<30} {b.period_type:<10} {_format_amount(b.amount):<12}"
        )
    logger.info(f"\nTotal budgets: {len(budgets)}")


def cmd_create(args, db_manager, config):
    categories_repo = CategoryRepository(db_manager)
    budgets_repo = BudgetRepository(db_manager)

    print("\nCreate New Budget")
    print("=" * 80)

    # Pick category
    all_categories = categories_repo.find_all()
    if not all_categories:
        logger.error("No categories found. Create a category first.")
        sys.exit(1)

    print("\nAvailable categories:")
    for c in all_categories:
        print(f"  {c.id}: {c.name}")

    cat_input = input("\nCategory ID: ").strip()
    try:
        category_id = int(cat_input)
    except ValueError:
        logger.error("Category ID must be a number.")
        sys.exit(1)

    category = categories_repo.find(category_id)
    if not category:
        logger.error(f"Category with ID {category_id} not found.")
        sys.exit(1)

    # Pick period type
    period_type = input("Period type (monthly/yearly): ").strip().lower()
    if period_type not in VALID_PERIOD_TYPES:
        logger.error(
            f"Invalid period type. Must be one of: {', '.join(VALID_PERIOD_TYPES)}"
        )
        sys.exit(1)

    # Enter amount
    amount_input = input("Amount (in dollars, e.g. 500.00): ").strip()
    try:
        amount_dollars = float(amount_input)
        amount_cents = int(round(amount_dollars * 100))
    except ValueError:
        logger.error("Amount must be a number.")
        sys.exit(1)

    if amount_cents <= 0:
        logger.error("Amount must be greater than zero.")
        sys.exit(1)

    try:
        budget = budgets_repo.create(category_id, period_type, amount_cents)
        logger.info(f"\n✓ Budget created successfully with ID: {budget.id}")
        logger.info(f"  Category: {budget.category_name}")
        logger.info(f"  Period: {budget.period_type}")
        logger.info(f"  Amount: {_format_amount(budget.amount)}")
    except Exception as e:
        logger.error(f"Error creating budget: {e}")
        sys.exit(1)


def cmd_delete(args, db_manager, config):
    budgets_repo = BudgetRepository(db_manager)
    budget_id = args.budget_id

    budget = budgets_repo.find(budget_id)
    if not budget:
        logger.error(f"Budget with ID {budget_id} not found.")
        sys.exit(1)

    logger.info("\nBudget to delete:")
    logger.info(f"  ID: {budget.id}")
    logger.info(f"  Category: {budget.category_name}")
    logger.info(f"  Period: {budget.period_type}")
    logger.info(f"  Amount: {_format_amount(budget.amount)}")

    confirm = (
        input("\nAre you sure you want to delete this budget? (yes/no): ")
        .strip()
        .lower()
    )
    if confirm != "yes":
        logger.info("Deletion cancelled.")
        return

    if budgets_repo.delete(budget_id):
        logger.info("✓ Budget deleted successfully.")
    else:
        logger.error("Failed to delete budget.")
        sys.exit(1)


def cmd_modify(args, db_manager, config):
    budgets_repo = BudgetRepository(db_manager)
    budget_id = args.budget_id

    budget = budgets_repo.find(budget_id)
    if not budget:
        logger.error(f"Budget with ID {budget_id} not found.")
        sys.exit(1)

    try:
        amount_dollars = float(args.amount)
        amount_cents = int(round(amount_dollars * 100))
    except ValueError:
        logger.error("Amount must be a number.")
        sys.exit(1)

    if amount_cents <= 0:
        logger.error("Amount must be greater than zero.")
        sys.exit(1)

    updated = budgets_repo.update_amount(budget_id, amount_cents)
    if not updated:
        logger.error("Failed to update budget.")
        sys.exit(1)

    logger.info("✓ Budget updated successfully.")
    logger.info(f"  Category: {updated.category_name}")
    logger.info(f"  Period: {updated.period_type}")
    logger.info(f"  Amount: {_format_amount(updated.amount)}")


def setup_parser(subparsers):
    parser = subparsers.add_parser(
        "budgets",
        help="Manage budgets",
        description="Create, list, modify, and delete spending budgets",
    )

    budgets_subparsers = parser.add_subparsers(
        title="subcommands",
        description="Available budget commands",
        dest="subcommand",
        required=True,
    )

    list_parser = budgets_subparsers.add_parser("list", help="List all budgets")
    list_parser.set_defaults(func=cmd_list)

    create_parser = budgets_subparsers.add_parser(
        "create", help="Create a new budget interactively"
    )
    create_parser.set_defaults(func=cmd_create)

    delete_parser = budgets_subparsers.add_parser(
        "delete", help="Delete a budget by ID"
    )
    delete_parser.add_argument("budget_id", type=int, help="ID of the budget to delete")
    delete_parser.set_defaults(func=cmd_delete)

    modify_parser = budgets_subparsers.add_parser(
        "modify", help="Modify a budget's amount"
    )
    modify_parser.add_argument("budget_id", type=int, help="ID of the budget to modify")
    modify_parser.add_argument(
        "--amount", required=True, help="New amount in dollars (e.g. 500.00)"
    )
    modify_parser.set_defaults(func=cmd_modify)
