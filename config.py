"""Configuration management for Necker.

Reads configuration from ~/.config/necker.toml and creates default config if needed.
"""

from pathlib import Path
from dataclasses import dataclass
import tomllib
import tomli_w


@dataclass
class Config:
    """Application configuration."""

    base_dir: Path
    db_data_dir: Path
    db_filename: str
    log_level: str
    log_dir: Path
    archive_enabled: bool
    archive_dir: Path

    @property
    def db_path(self) -> Path:
        """Get the full database path (data_dir/filename)."""
        return self.db_data_dir / self.db_filename

    @classmethod
    def default(cls) -> "Config":
        """Create a Config with default values."""
        home = Path.home()
        base_dir = home / "data" / "necker"
        return cls(
            base_dir=base_dir,
            db_data_dir=base_dir / "db",
            db_filename="necker.db",
            log_level="INFO",
            log_dir=base_dir / "logs",
            archive_enabled=True,
            archive_dir=base_dir / "archives",
        )


def get_config_path() -> Path:
    """Get the path to the config file."""
    return Path.home() / ".config" / "necker.toml"


def get_migrations_dir() -> Path:
    """Get the path to the migrations directory.

    This is always relative to the code location, not configurable.
    """
    return Path(__file__).parent / "db" / "migrations"


def load_config() -> Config:
    """Load configuration from file, creating default if it doesn't exist.

    Returns:
        Config object with loaded or default values.
    """
    config_path = get_config_path()

    # If config doesn't exist, create it with defaults
    if not config_path.exists():
        config = Config.default()
        _write_config(config)
        return config

    # Load existing config
    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    # Parse with defaults for any missing values
    base_dir = Path(data.get("base_dir", Path.home() / "data" / "necker"))

    db_config = data.get("database", {})
    db_data_dir = Path(db_config.get("data_dir", base_dir / "db"))
    db_filename = db_config.get("filename", "necker.db")

    log_config = data.get("logging", {})
    log_level = log_config.get("level", "INFO")
    log_dir = Path(log_config.get("log_dir", base_dir / "logs"))

    archive_config = data.get("archive", {})
    archive_enabled = archive_config.get("enabled", True)
    archive_dir = Path(archive_config.get("archive_dir", base_dir / "archives"))

    return Config(
        base_dir=base_dir,
        db_data_dir=db_data_dir,
        db_filename=db_filename,
        log_level=log_level,
        log_dir=log_dir,
        archive_enabled=archive_enabled,
        archive_dir=archive_dir,
    )


def _write_config(config: Config) -> None:
    """Write config to the config file.

    Args:
        config: Config object to write.
    """
    config_path = get_config_path()

    # Ensure config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert config to TOML structure
    data = {
        "base_dir": str(config.base_dir),
        "database": {
            "data_dir": str(config.db_data_dir),
            "filename": config.db_filename,
        },
        "logging": {
            "level": config.log_level,
            "log_dir": str(config.log_dir),
        },
        "archive": {
            "enabled": config.archive_enabled,
            "archive_dir": str(config.archive_dir),
        },
    }

    # Write TOML file
    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)
