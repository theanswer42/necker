#!/usr/bin/env python3
"""
Necker CLI - Unified command-line interface for managing accounts and transactions.

Usage:
    python -m cli <command> <subcommand> [options]

Commands:
    accounts     Manage accounts
    transactions Import and manage transactions
    reports      Run analytical reports
    migrate      Database migrations
    backup       Back up the database

Examples:
    python -m cli accounts list
    python -m cli accounts create
    python -m cli transactions ingest file.csv --account-name bofa
    python -m cli reports spending-summary --month 2024/01 --basis cash
    python -m cli migrate status
    python -m cli migrate apply
    python -m cli backup /path/to/backup.db
"""

import sys
import argparse
from cli import (
    accounts,
    transactions,
    migrate,
    categories,
    server,
    budgets,
    backup,
    reports,
)
from cli.output import OutputWriter, TextRenderer
from config import load_config
from db.manager import DatabaseManager
from logger import get_logger, setup_logging


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
    categories.setup_parser(subparsers)
    budgets.setup_parser(subparsers)
    reports.setup_parser(subparsers)
    migrate.setup_parser(subparsers)
    backup.setup_parser(subparsers)
    server.setup_parser(subparsers)

    # Parse arguments and execute
    args = parser.parse_args()

    # Call the appropriate handler function
    if hasattr(args, "func"):
        try:
            # Load configuration
            config = load_config()

            # Set up logging
            setup_logging(config)

            # Create database manager
            db_manager = DatabaseManager(config)

            # Writer for typed data output (stdout)
            output = OutputWriter(TextRenderer())

            if args.command in (
                "accounts",
                "transactions",
                "categories",
                "budgets",
                "reports",
            ):
                args.func(args, db_manager, config, output)
            elif args.command == "serve":
                args.func(args, db_manager, config)
            elif args.command in ("migrate", "backup"):
                args.func(args, db_manager, output)
            else:
                args.func(args, output)
        except Exception as e:
            get_logger().error(f"Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
