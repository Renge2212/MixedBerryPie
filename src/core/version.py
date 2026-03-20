"""
Version information for MixedBerryPie application.

The version is read dynamically from the installed package metadata
(set by pyproject.toml). This ensures pyproject.toml is the single
source of truth and no manual sync is needed here.
"""

import tomllib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path


def _get_version() -> str:
    """Read version from package metadata or pyproject.toml as fallback."""
    try:
        # Works when installed via uv / pip (dev or production)
        return _pkg_version("mixedberrypie")
    except PackageNotFoundError:
        pass

    # Fallback: parse pyproject.toml directly.
    # Required when running as a PyInstaller-built executable where
    # importlib.metadata is unavailable.
    try:
        toml_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(toml_path, "rb") as f:
            return str(tomllib.load(f)["project"]["version"])
    except Exception:
        return "0.0.0"


__version__ = _get_version()
__author__ = "Renge2212"
__description__ = "Radial pie menu for quick keyboard shortcuts"
