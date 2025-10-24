from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()


def get_db_path() -> Path:
    """Get the path to the database file."""
    db_file = os.getenv("DB_FILE", "necker.db")
    return Path(__file__).parent / "db" / "data" / db_file


def get_environment() -> str:
    """Get the current environment."""
    return os.getenv("ENVIRONMENT", "development")


def get_migrations_dir() -> Path:
    """Get the path to the migrations directory."""
    return Path(__file__).parent / "db" / "migrations"
