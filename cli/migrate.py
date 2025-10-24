#!/usr/bin/env python3

import sys
import argparse
from db import manager as dbmgr


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


def get_available_migrations():
    migrations_dir = dbmgr.get_migrations_dir()
    if not migrations_dir.exists():
        return []

    migrations = []
    for file_path in migrations_dir.glob("*.sql"):
        migrations.append(file_path.name)

    return sorted(migrations)


def apply_migration(conn, migration_file):
    migrations_dir = dbmgr.get_migrations_dir()
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
        print(f"Applied migration: {migration_file}")
    except Exception as e:
        conn.rollback()
        print(f"Error applying migration {migration_file}: {e}")
        raise


def status():
    db_path = dbmgr.get_db_path()

    if not db_path.exists():
        print("Database does not exist. Run 'migrate' to create it.")
        return

    with dbmgr.connect() as conn:
        init_schema_migrations_table(conn)
        applied = get_applied_migrations(conn)
        available = get_available_migrations()

        print("Migration Status:")
        print("================")

        if not available:
            print("No migrations found.")
            return

        for migration in available:
            status_text = "APPLIED" if migration in applied else "PENDING"
            print(f"{migration}: {status_text}")

        pending_count = len([m for m in available if m not in applied])
        print(f"\nTotal migrations: {len(available)}")
        print(f"Applied: {len(applied)}")
        print(f"Pending: {pending_count}")


def migrate():
    with dbmgr.connect() as conn:
        init_schema_migrations_table(conn)
        applied = get_applied_migrations(conn)
        available = get_available_migrations()

        pending = [m for m in available if m not in applied]

        if not pending:
            print("No pending migrations.")
            return

        print(f"Applying {len(pending)} migration(s)...")

        for migration in pending:
            apply_migration(conn, migration)

        print(f"Successfully applied {len(pending)} migration(s).")


def main():
    parser = argparse.ArgumentParser(description="Database migration tool")
    parser.add_argument("command", choices=["status", "migrate"], help="Command to run")

    args = parser.parse_args()

    try:
        if args.command == "status":
            status()
        elif args.command == "migrate":
            migrate()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
