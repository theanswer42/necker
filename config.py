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

    db_path: Path

    @classmethod
    def default(cls) -> "Config":
        """Create a Config with default values."""
        home = Path.home()
        return cls(db_path=home / "data" / "necker" / "db" / "necker.db")


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

    return Config(db_path=Path(data["database"]["path"]))


def _write_config(config: Config) -> None:
    """Write config to the config file.

    Args:
        config: Config object to write.
    """
    config_path = get_config_path()

    # Ensure config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert config to TOML structure
    data = {"database": {"path": str(config.db_path)}}

    # Write TOML file
    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)

    print(f"Created default config file at: {config_path}")
