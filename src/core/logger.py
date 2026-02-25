import ctypes
import logging
import logging.handlers
import os
from pathlib import Path


def is_admin() -> bool:
    """Check if the current process has administrative privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


# Project root (base of MixedBerryPie directory)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Log storage: Use AppData on Windows to allow writing even when installed in Program Files
APP_NAME = "MixedBerryPie"
APPDATA = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
LOGS_DIR = Path(APPDATA) / APP_NAME / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

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


# Initialize the base logger on module import (needed for RotatingFileHandler)
# The directory creation is intentional: the app requires a writable log directory.
setup_logger()
logger = get_logger("core")
logger.debug("Logger module initialized — Log file: %s", LOG_FILE)
