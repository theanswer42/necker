#!/usr/bin/env python3
"""
Necker CLI - Unified command-line interface for managing accounts and transactions.

Usage:
    python -m cli <command> <subcommand> [options]

Commands:
    accounts     Manage accounts
    transactions Import and manage transactions
    migrate      Database migrations

Examples:
    python -m cli accounts list
    python -m cli accounts create
    python -m cli transactions ingest file.csv --account-name bofa
    python -m cli migrate status
    python -m cli migrate apply
"""

import sys
import argparse
from cli import accounts, transactions, migrate


def main():
    """Main CLI entry point with subcommands."""
    parser = argparse.ArgumentParser(
        prog="cli",
        description="Necker - Personal finance transaction management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Create subparsers for each command
    subparsers = parser.add_subparsers(
        title="commands",
        description="Available commands",
        dest="command",
        required=True,
    )

    # Register each command's subparser
    accounts.setup_parser(subparsers)
    transactions.setup_parser(subparsers)
    migrate.setup_parser(subparsers)

    # Parse arguments and execute
    args = parser.parse_args()

    # Call the appropriate handler function
    if hasattr(args, "func"):
        try:
            args.func(args)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
