import logging
import logging.handlers
import os
from pathlib import Path

# Log storage: Use AppData on Windows to allow writing even when installed in Program Files
APP_NAME = "MixedBerryPie"
APPDATA = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
LOGS_DIR = Path(APPDATA) / APP_NAME / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Log file path
LOG_FILE = LOGS_DIR / "mixedberrypie.log"

# Log level constants


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger with the given name.

    Sets up a logger with both console and file handlers.
    The file handler uses a rotating file to manage log size.

    Args:
        name: Name for the logger (usually __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # If logger already has handlers, don't add more (avoid duplicate logs)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)
    logger.addHandler(console_handler)

    # File handler (Rotating)
    # Max 5MB per file, keep 3 backups
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    return logger


def setup_logger() -> None:
    """Initialize the base 'piemenu' logger with handlers.

    This ensures that all child loggers (e.g., 'piemenu.app')
    inherit these settings.
    """
    get_logger("piemenu")
