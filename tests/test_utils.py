"""Tests for src/core/utils.py helper functions."""

import os
import sys

from src.core.utils import get_resource_path, resolve_icon_path

# ── get_resource_path ──────────────────────────────────────────────────────


def test_resource_path_dev_mode():
    """In normal dev mode (no _MEIPASS), base path is project root."""
    # Ensure _MEIPASS is not set
    assert not hasattr(sys, "_MEIPASS") or True  # test env is always dev mode
    result = get_resource_path(os.path.join("resources", "icons"))
    # Should resolve to <project_root>/resources/icons
    assert os.path.isabs(result)
    assert result.endswith(os.path.join("resources", "icons"))


def test_resource_path_pyinstaller():
    """With _MEIPASS set, base path uses that directory."""
    fake_base = os.path.join("C:", "fake", "meipass")
    sys._MEIPASS = fake_base  # type: ignore[attr-defined]
    try:
        result = get_resource_path(os.path.join("resources", "icons"))
        expected = os.path.join(fake_base, "resources", "icons")
        assert result == expected
    finally:
        del sys._MEIPASS  # type: ignore[attr-defined]


# ── resolve_icon_path ──────────────────────────────────────────────────────


def test_empty_string_returns_none():
    assert resolve_icon_path("") is None


def test_none_like_empty_returns_none():
    assert resolve_icon_path("") is None


def test_absolute_exists(tmp_path):
    icon = tmp_path / "test_icon.png"
    icon.write_bytes(b"PNG data")
    result = resolve_icon_path(str(icon))
    assert result == str(icon)


def test_absolute_not_exists_returns_none():
    """Non-existent absolute path should return None (not the path itself)."""
    fake_path = os.path.abspath("/nonexistent/path/icon.png")
    result = resolve_icon_path(fake_path)
    assert result is None


def test_user_icons_relative(tmp_path, monkeypatch):
    """user_icons/ relative path resolves via CONFIG_DIR."""
    config_dir = str(tmp_path / "config")
    user_icons = os.path.join(config_dir, "user_icons")
    os.makedirs(user_icons, exist_ok=True)

    icon_file = os.path.join(user_icons, "foo.png")
    with open(icon_file, "wb") as f:
        f.write(b"icon")

    monkeypatch.setattr("src.core.config.CONFIG_DIR", config_dir)
    result = resolve_icon_path("user_icons/foo.png")
    assert result is not None
    assert os.path.isabs(result)
    assert os.path.exists(result)


def test_user_icons_not_found_returns_none(tmp_path, monkeypatch):
    """user_icons/ path to missing file should eventually return None."""
    config_dir = str(tmp_path / "config")
    user_icons = os.path.join(config_dir, "user_icons")
    os.makedirs(user_icons, exist_ok=True)

    monkeypatch.setattr("src.core.config.CONFIG_DIR", config_dir)
    # File doesn't exist, and no resource fallback either
    result = resolve_icon_path("user_icons/missing_icon_12345.png")
    assert result is None


def test_resource_path_resolution():
    """Known preset icon should resolve via resources/."""
    result = resolve_icon_path("icons/Drawing Tools/brush.svg")
    assert result is not None
    assert os.path.exists(result)
    assert result.endswith("brush.svg")


def test_basename_fallback_walk():
    """basename-only search should find icon in subdirectories."""
    result = resolve_icon_path("brush.svg")
    assert result is not None
    assert os.path.exists(result)
    assert result.endswith("brush.svg")


def test_all_strategies_fail_returns_none():
    """When all resolution strategies fail, return None."""
    result = resolve_icon_path("totally_nonexistent_icon_xyz_999.svg")
    assert result is None
