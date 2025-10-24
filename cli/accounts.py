#!/usr/bin/env python3

import sys
import argparse
from ingestion import get_available_modules
from services import accounts as account_service


def list_accounts():
    """List all accounts in the database."""
    accounts = account_service.find_all()

    if not accounts:
        print("No accounts found.")
        return

    print("\nAccounts:")
    print("=" * 80)
    for account in accounts:
        print(f"ID: {account.id}")
        print(f"Name: {account.name}")
        print(f"Type: {account.type}")
        print(f"Description: {account.description}")
        print("-" * 80)

    print(f"\nTotal accounts: {len(accounts)}")


def create_account():
    """Interactively create a new account."""
    available_types = get_available_modules()

    print("\nCreate New Account")
    print("=" * 80)

    # Get account name
    name = input("Account name (e.g., bofa_checking): ").strip()
    if not name:
        print("Error: Account name cannot be empty.")
        sys.exit(1)

    # Get account type
    print(f"\nAvailable account types: {', '.join(available_types)}")
    account_type = input("Account type: ").strip()
    if account_type not in available_types:
        print(f"Error: Invalid account type '{account_type}'.")
        print(f"Must be one of: {', '.join(available_types)}")
        sys.exit(1)

    # Get description
    description = input(
        "Description (e.g., Bank of America Checking Account): "
    ).strip()
    if not description:
        print("Error: Description cannot be empty.")
        sys.exit(1)

    # Create account via service
    try:
        account = account_service.create(name, account_type, description)

        print(f"\n✓ Account created successfully with ID: {account.id}")
        print(f"  Name: {account.name}")
        print(f"  Type: {account.type}")
        print(f"  Description: {account.description}")

    except Exception as e:
        print(f"\nError creating account: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Account management CLI")
    parser.add_argument(
        "--list-accounts", action="store_true", help="List all accounts"
    )
    parser.add_argument(
        "--create-account",
        action="store_true",
        help="Create a new account interactively",
    )

    args = parser.parse_args()

    # Ensure at least one command is specified
    if not args.list_accounts and not args.create_account:
        parser.print_help()
        sys.exit(1)

    try:
        if args.list_accounts:
            list_accounts()
        elif args.create_account:
            create_account()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
