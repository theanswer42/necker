#!/usr/bin/env python3

from logger import get_logger

logger = get_logger()


def init_schema_migrations_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_file TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def get_applied_migrations(conn):
    cursor = conn.execute(
        "SELECT migration_file FROM schema_migrations ORDER BY migration_file"
    )
    return {row[0] for row in cursor.fetchall()}


def get_available_migrations(db_manager):
    migrations_dir = db_manager.get_migrations_dir()
    if not migrations_dir.exists():
        return []

    migrations = []
    for file_path in migrations_dir.glob("*.sql"):
        migrations.append(file_path.name)

    return sorted(migrations)


def apply_migration(conn, migration_file, db_manager):
    migrations_dir = db_manager.get_migrations_dir()
    migration_path = migrations_dir / migration_file

    with open(migration_path, "r") as f:
        sql = f.read()

    try:
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations (migration_file) VALUES (?)",
            (migration_file,),
        )
        conn.commit()
        logger.info(f"Applied migration: {migration_file}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error applying migration {migration_file}: {e}")
        raise


def cmd_status(args, db_manager):
    """Show migration status."""
    db_path = db_manager.get_db_path()

    if not db_path.exists():
        logger.info(
            "Database does not exist. Run 'python -m cli migrate apply' to create it."
        )
        return

    with db_manager.connect() as conn:
        init_schema_migrations_table(conn)
        applied = get_applied_migrations(conn)
        available = get_available_migrations(db_manager)

        logger.info("Migration Status:")
        logger.info("================")

        if not available:
            logger.info("No migrations found.")
            return

        for migration in available:
            status_text = "APPLIED" if migration in applied else "PENDING"
            logger.info(f"{migration}: {status_text}")

        pending_count = len([m for m in available if m not in applied])
        logger.info(f"\nTotal migrations: {len(available)}")
        logger.info(f"Applied: {len(applied)}")
        logger.info(f"Pending: {pending_count}")


def cmd_apply(args, db_manager):
    """Apply pending migrations."""
    with db_manager.connect() as conn:
        init_schema_migrations_table(conn)
        applied = get_applied_migrations(conn)
        available = get_available_migrations(db_manager)

        pending = [m for m in available if m not in applied]

        if not pending:
            logger.info("No pending migrations.")
            return

        logger.info(f"Applying {len(pending)} migration(s)...")

        for migration in pending:
            apply_migration(conn, migration, db_manager)

        logger.info(f"Successfully applied {len(pending)} migration(s).")


def setup_parser(subparsers):
    """Setup migrate subcommand parser.

    Args:
        subparsers: The subparsers object from the main CLI
    """
    parser = subparsers.add_parser(
        "migrate",
        help="Database migrations",
        description="Manage database schema migrations",
    )

    # Add subcommands for migrate
    migrate_subparsers = parser.add_subparsers(
        title="subcommands",
        description="Available migration commands",
        dest="subcommand",
        required=True,
    )

    # migrate status
    status_parser = migrate_subparsers.add_parser(
        "status", help="Show migration status"
    )
    status_parser.set_defaults(func=cmd_status)

    # migrate apply
    apply_parser = migrate_subparsers.add_parser(
        "apply", help="Apply pending migrations"
    )
    apply_parser.set_defaults(func=cmd_apply)
