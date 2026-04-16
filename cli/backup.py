#!/usr/bin/env python3
"""Backup the configured database to a user-provided path."""

from pathlib import Path

from logger import get_logger

logger = get_logger()


def cmd_backup(args, db_manager):
    """Back up the configured database to args.output_path."""
    output_path = Path(args.output_path).resolve()
    db_manager.backup_to(output_path)
    logger.info(f"Backed up database to {output_path}")


def setup_parser(subparsers):
    """Setup backup subcommand parser.

    Args:
        subparsers: The subparsers object from the main CLI
    """
    parser = subparsers.add_parser(
        "backup",
        help="Back up the database",
        description="Back up the configured database to a file using SQLite's online backup API",
    )
    parser.add_argument(
        "output_path",
        help="Path where the backup file will be written (must not already exist)",
    )
    parser.set_defaults(func=cmd_backup)
