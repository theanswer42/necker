#!/usr/bin/env python3

import sys
from ingestion import get_available_modules
from logger import get_logger

logger = get_logger()


def cmd_list(args, services):
    """List all accounts in the database."""
    accounts = services.accounts.find_all()

    if not accounts:
        logger.info("No accounts found.")
        return

    logger.info("\nAccounts:")
    logger.info("=" * 80)
    for account in accounts:
        logger.info(f"ID: {account.id}")
        logger.info(f"Name: {account.name}")
        logger.info(f"Type: {account.account_type}")
        logger.info(f"Description: {account.description}")
        logger.info("-" * 80)

    logger.info(f"\nTotal accounts: {len(accounts)}")


def cmd_create(args, services):
    """Interactively create a new account."""
    from services.accounts import create_account

    available_types = get_available_modules()

    print("\nCreate New Account")
    print("=" * 80)

    name = input("Account name (e.g., bofa_checking): ").strip()

    print(f"\nAvailable account types: {', '.join(available_types)}")
    account_type = input("Account type: ").strip()

    description = input(
        "Description (e.g., Bank of America Checking Account): "
    ).strip()

    try:
        account = create_account(services, name, account_type, description)

        logger.info(f"\n✓ Account created successfully with ID: {account.id}")
        logger.info(f"  Name: {account.name}")
        logger.info(f"  Type: {account.account_type}")
        logger.info(f"  Description: {account.description}")

    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)


def setup_parser(subparsers):
    """Setup accounts subcommand parser.

    Args:
        subparsers: The subparsers object from the main CLI
    """
    parser = subparsers.add_parser(
        "accounts",
        help="Manage accounts",
        description="Create and list financial accounts",
    )

    # Add subcommands for accounts
    accounts_subparsers = parser.add_subparsers(
        title="subcommands",
        description="Available account commands",
        dest="subcommand",
        required=True,
    )

    # accounts list
    list_parser = accounts_subparsers.add_parser("list", help="List all accounts")
    list_parser.set_defaults(func=cmd_list)

    # accounts create
    create_parser = accounts_subparsers.add_parser(
        "create", help="Create a new account interactively"
    )
    create_parser.set_defaults(func=cmd_create)
