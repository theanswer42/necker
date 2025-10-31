#!/usr/bin/env python3
"""Reset script for Necker.

This script will:
1. Delete the data directory (including database, logs, and archives)
2. Run migrations to create a fresh database
"""

import shutil
import sys

from config import load_config
from db.manager import DatabaseManager
from cli.migrate import cmd_apply


def reset():
    """Reset the application state."""
    print("Necker Reset Script")
    print("=" * 50)

    # Load configuration
    config = load_config()

    # Check if reset is enabled
    if not config.enable_reset:
        print("\nReset is disabled in configuration (enable_reset=false).")
        print("To enable reset, set enable_reset=true in ~/.config/necker.toml")
        sys.exit(1)

    # Show what will be deleted
    print(f"\nData directory: {config.base_dir}")
    print(f"Database: {config.db_path}")
    print(f"Logs: {config.log_dir}")
    print(f"Archives: {config.archive_dir}")

    # Confirm with user
    response = input("\nThis will delete ALL data. Continue? (yes/no): ")
    if response.lower() != "yes":
        print("Reset cancelled.")
        sys.exit(0)

    # Delete the data directory
    if config.base_dir.exists():
        print(f"\nDeleting {config.base_dir}...")
        shutil.rmtree(config.base_dir)
        print("✓ Data directory deleted")
    else:
        print(f"\n✓ Data directory does not exist: {config.base_dir}")

    # Run migrations to create database
    print("\nRunning migrations...")
    db_manager = DatabaseManager(config)

    # Create a minimal args object for cmd_apply
    class Args:
        pass

    args = Args()
    cmd_apply(args, db_manager)

    print("\n" + "=" * 50)
    print("Reset complete! Database has been recreated.")
    print(f"Database location: {config.db_path}")


if __name__ == "__main__":
    reset()
