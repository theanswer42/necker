#!/usr/bin/env python3
"""Reset script for Necker.

This script will:
1. Delete the data directory (including database, logs, and archives)
2. Run migrations to create a fresh database
"""

import shutil
import sys

from cli.migrate import cmd_apply
from cli.output import OutputWriter, TextRenderer
from config import load_config
from db.manager import DatabaseManager
from logger import get_logger, setup_logging


def reset():
    """Reset the application state."""
    # Load configuration
    config = load_config()

    # Set up logging so status/progress goes through the logger
    setup_logging(config)
    logger = get_logger()

    # Check if reset is enabled
    if not config.enable_reset:
        logger.error("Reset is disabled in configuration (enable_reset=false).")
        logger.error("To enable reset, set enable_reset=true in ~/.config/necker.toml")
        sys.exit(1)

    # Show what will be deleted (interactive context for the prompt)
    print("Necker Reset Script")
    print("=" * 50)
    print(f"\nData directory: {config.base_dir}")
    print(f"Database: {config.db_path}")
    print(f"Logs: {config.log_dir}")
    print(f"Archives: {config.archive_dir}")

    # Confirm with user
    response = input("\nThis will delete ALL data. Continue? (yes/no): ")
    if response.lower() != "yes":
        logger.info("Reset cancelled.")
        sys.exit(0)

    # Delete the data directory
    if config.base_dir.exists():
        logger.info(f"Deleting {config.base_dir}...")
        shutil.rmtree(config.base_dir)
        logger.info("✓ Data directory deleted")
    else:
        logger.info(f"✓ Data directory does not exist: {config.base_dir}")

    # Run migrations to create database
    logger.info("Running migrations...")
    db_manager = DatabaseManager(config)

    # Create a minimal args object for cmd_apply
    class Args:
        pass

    args = Args()
    output = OutputWriter(TextRenderer())
    cmd_apply(args, db_manager, output)

    logger.info("Reset complete. Database has been recreated.")
    logger.info(f"Database location: {config.db_path}")


if __name__ == "__main__":
    reset()
