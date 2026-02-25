"""Utility functions for resource path resolution.

Provides functions to locate resources in both development and
PyInstaller bundled environments.
"""

import os
import sys

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment]


def is_dark_mode() -> bool:
    """Check Windows registry for dark mode preference.

    Returns:
        True if the user prefers dark mode, False otherwise.
        Defaults to True on error or non-Windows platforms.
    """
    if winreg is None:
        return True

    try:
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(
            registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return bool(value == 0)
    except Exception:
        return True  # Default to dark


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller.

    Args:
        relative_path: Path relative to project root

    Returns:
        Absolute path to the resource

    Note:
        In PyInstaller bundles, uses sys._MEIPASS as base path.
        In development, uses project root directory.
    """
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    else:
        # Normal python environment
        # src/core/utils.py -> src/core -> src -> (project root)
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    return os.path.join(base_path, relative_path)


def resolve_icon_path(path: str) -> str | None:
    """Resolve icon path to absolute path.

    Args:
        path: Icon path (absolute or relative)

    Returns:
        Absolute path to icon, or None if path is empty
    """
    if not path:
        return None

    # If absolute path exists, use it
    if os.path.isabs(path) and os.path.exists(path):
        return path

    # Try resolving 'user_icons/' relative paths (Managed by Smart Icon Library)
    if path.startswith("user_icons"):
        config_dir = None
        try:
            from src.core.config import CONFIG_DIR

            config_dir = CONFIG_DIR
        except (ImportError, AttributeError):
            # Fallback calculation to avoid circular imports
            app_name = "MixedBerryPie"
            appdata = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
            config_dir = os.path.join(appdata, app_name)

        if config_dir:
            managed_path = os.path.join(config_dir, path)
            if os.path.exists(managed_path):
                return os.path.abspath(managed_path)

    # Try resolving as resource (e.g. presets 'icons/Drawing Tools/pencil.svg')
    resource_path = get_resource_path(os.path.join("resources", path))
    if os.path.exists(resource_path):
        return resource_path

    # Special case: check resources/icons directly for legacy reasons or presets
    if not path.startswith("icons/"):
        preset_path = get_resource_path(os.path.join("resources", "icons", path))
        if os.path.exists(preset_path):
            return preset_path

    # Fallback for old configs where icons were flat inside resources/icons
    basename = os.path.basename(path)
    icons_dir = get_resource_path(os.path.join("resources", "icons"))
    if os.path.exists(icons_dir):
        for root, _, files in os.walk(icons_dir):
            if basename in files:
                return os.path.join(root, basename)

    # Return original if resolution fails (it might be an absolute path that doesn't exist yet)
    return path
