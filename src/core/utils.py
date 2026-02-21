"""Utility functions for resource path resolution.

Provides functions to locate resources in both development and
PyInstaller bundled environments.
"""

import os
import sys


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

    Note:
        If path is absolute and exists, returns it as-is.
        If path is relative (e.g. 'icons/foo.svg'), resolves against resources directory.
        Returns original path if resolution fails (might be valid but temporarily missing).
    """
    if not path:
        return None

    # If absolute path exists, use it
    if os.path.isabs(path) and os.path.exists(path):
        return path

    # Try resolving as resource
    resource_path = get_resource_path(os.path.join("resources", path))
    if os.path.exists(resource_path):
        return resource_path

    # Return original if resolution fails
    return path
