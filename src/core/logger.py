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

# Root logger name for the application
_ROOT_LOGGER = "piemenu"


class SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Windows-safe rotating file handler.

    The standard RotatingFileHandler fails on Windows with WinError 32
    because it tries to rename an open file. This subclass closes the
    file stream before rotating, which avoids the lock conflict.
    """

    def doRollover(self) -> None:
        if self.stream:
            self.stream.close()
            self.stream = None  # type: ignore[assignment]
        super().doRollover()


def setup_logger() -> None:
    """Initialize the base 'piemenu' logger with handlers.

    File and console handlers are attached ONLY to this root logger.
    All child loggers (e.g., 'piemenu.app') inherit via propagation,
    so only one file handle is ever open at a time — avoiding WinError 32
    on Windows when the rotating handler tries to rename the log file.
    """
    root = logging.getLogger(_ROOT_LOGGER)

    if root.handlers:
        return  # Already configured

    root.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler (warnings and above)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)
    root.addHandler(console_handler)


_FILE_HANDLER = None


def set_file_logging(enable: bool) -> None:
    """Enable or disable file logging.

    Adjusts the log level to INFO instead of DEBUG to reduce log volume.
    Decreases backupCount to 2 and maxBytes to 2MB to save space.
    """
    global _FILE_HANDLER
    root = logging.getLogger(_ROOT_LOGGER)

    if enable:
        if _FILE_HANDLER is None:
            _FILE_HANDLER = SafeRotatingFileHandler(
                LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
            )
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
            _FILE_HANDLER.setFormatter(formatter)
            _FILE_HANDLER.setLevel(logging.INFO)  # Changed from DEBUG to INFO to save space
            root.addHandler(_FILE_HANDLER)
    elif _FILE_HANDLER is not None:
        root.removeHandler(_FILE_HANDLER)
        _FILE_HANDLER.close()
        _FILE_HANDLER = None


def get_logger(name: str) -> logging.Logger:
    """Get a named child logger under the 'piemenu' namespace.

    The logger propagates to the root 'piemenu' logger which holds the
    actual handlers. No additional handlers are added here.

    The name is automatically placed under the 'piemenu' hierarchy so
    that propagation works regardless of what name is passed in:
      - 'piemenu.app'          -> used as-is
      - 'src.core.hook_manager'-> becomes 'piemenu.src.core.hook_manager'
      - 'win32_input'          -> becomes 'piemenu.win32_input'

    Args:
        name: Logger name (e.g. __name__ or 'piemenu.app')

    Returns:
        Logger instance that propagates to the piemenu root logger
    """
    # Ensure the root logger is configured before returning any child
    setup_logger()
    # Ensure the name is under the piemenu hierarchy
    if not name.startswith(_ROOT_LOGGER):
        name = f"{_ROOT_LOGGER}.{name}"
    return logging.getLogger(name)
