"""Logging configuration for Necker.

Sets up logging to both file (with date-based naming) and console.
"""

import logging
from datetime import date
from config import Config


def setup_logging(config: Config) -> logging.Logger:
    """Set up application logging with file and console handlers.

    Args:
        config: Application configuration containing log settings.

    Returns:
        Configured logger instance.
    """
    # Create log directory if it doesn't exist
    config.log_dir.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger("necker")
    logger.setLevel(config.log_level)

    # Clear any existing handlers (in case this is called multiple times)
    logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_formatter = logging.Formatter("%(levelname)s - %(message)s")

    # File handler - logs to necker-{date}.log
    log_filename = f"necker-{date.today().isoformat()}.log"
    log_file_path = config.log_dir / log_filename
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(config.log_level)
    file_handler.setFormatter(detailed_formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(config.log_level)
    console_handler.setFormatter(console_formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger() -> logging.Logger:
    """Get the application logger.

    Returns:
        The necker logger instance.
    """
    return logging.getLogger("necker")
