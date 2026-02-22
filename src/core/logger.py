"""Logging configuration for MixedBerryPie application.

Provides structured logging with file rotation and configurable levels.
All modules should use get_logger(__name__) to obtain a logger instance.
"""

import ctypes
import logging
import logging.handlers
from pathlib import Path


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


# Project root (base of MixedBerryPie directory)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Create logs directory at root
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Log file path
LOG_FILE = LOGS_DIR / "mixedberrypie.log"

# Log level constants
LOG_LEVEL_DEBUG = logging.DEBUG
LOG_LEVEL_INFO = logging.INFO
LOG_LEVEL_WARNING = logging.WARNING
LOG_LEVEL_ERROR = logging.ERROR

# File rotation settings
MAX_LOG_SIZE_MB = 1
BACKUP_COUNT = 3


def setup_logger(name: str = "piemenu", level: int = logging.DEBUG) -> logging.Logger:
    """Setup logger with file rotation and console output.

    Args:
        name: Logger name (default: 'piemenu')
        level: Logging level (default: logging.INFO)

    Returns:
        Configured logger instance
    """
    # Use the root logger or a named base logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Format for log messages
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler with rotation (max 5MB, keep 5 backup files)
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not setup file logging: {e}")

    # Console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # Only warnings and above to console
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Get or create logger instance under the 'piemenu' hierarchy.

    Args:
        name: Module name (typically __name__). If None, returns root logger.

    Returns:
        Logger instance with hierarchical naming
    """
    if name is None or name == "piemenu":
        return logging.getLogger("piemenu")

    # Ensure hierarchical naming
    if not name.startswith("piemenu."):
        # Handle __name__ which might be 'src.core.config' -> 'piemenu.src.core.config'
        name = f"piemenu.{name}"

    return logging.getLogger(name)


# Initialize the base logger
setup_logger()
logger = get_logger("core")

# Log startup
logger.info("=" * 60)
logger.info("MixedBerryPie Logger Initialized")
logger.info(f"Log file: {LOG_FILE}")
logger.info(f"Process Elevation (Admin): {is_admin()}")
logger.info("=" * 60)
