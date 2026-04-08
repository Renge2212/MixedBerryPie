"""Tests for config.py helper functions extracted during refactoring."""

import hashlib
import os

import pytest

from src.core.config import (
    _copy_with_collision_handling,
    _find_duplicate_in_dir,
    _hash_file,
    _icon_path_to_abs,
    _normalize_icon_path,
    _validate_setting_type,
    add_to_icon_history,
)

# ── _hash_file ───────────────────────────────────────────────────────────────


def test_hash_file_known_content(tmp_path):
    f = tmp_path / "test.bin"
    f.write_bytes(b"hello world")
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert _hash_file(str(f)) == expected


def test_hash_file_empty_file(tmp_path):
    f = tmp_path / "empty.bin"
    f.write_bytes(b"")
    expected = hashlib.sha256(b"").hexdigest()
    assert _hash_file(str(f)) == expected


def test_hash_file_large_file(tmp_path):
    """File larger than _HASH_CHUNK_SIZE (65536) to verify chunked reading."""
    data = b"x" * 100_000
    f = tmp_path / "large.bin"
    f.write_bytes(data)
    expected = hashlib.sha256(data).hexdigest()
    assert _hash_file(str(f)) == expected


# ── _find_duplicate_in_dir ───────────────────────────────────────────────────


def test_find_duplicate_match(tmp_path):
    content = b"duplicate content"
    (tmp_path / "existing.png").write_bytes(content)
    src_hash = hashlib.sha256(content).hexdigest()
    result = _find_duplicate_in_dir(str(tmp_path), src_hash)
    assert result is not None
    assert os.path.basename(result) == "existing.png"


def test_find_duplicate_no_match(tmp_path):
    (tmp_path / "other.png").write_bytes(b"different content")
    src_hash = hashlib.sha256(b"not matching").hexdigest()
    assert _find_duplicate_in_dir(str(tmp_path), src_hash) is None


def test_find_duplicate_empty_dir(tmp_path):
    assert _find_duplicate_in_dir(str(tmp_path), "abc123") is None


def test_find_duplicate_ignores_subdirs(tmp_path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    src_hash = hashlib.sha256(b"anything").hexdigest()
    assert _find_duplicate_in_dir(str(tmp_path), src_hash) is None


# ── _copy_with_collision_handling ────────────────────────────────────────────


def test_copy_no_collision(tmp_path):
    src = tmp_path / "source" / "icon.png"
    src.parent.mkdir()
    src.write_bytes(b"icon data")
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    result = _copy_with_collision_handling(str(src), str(dest_dir))
    assert os.path.basename(result) == "icon.png"
    assert os.path.exists(result)
    with open(result, "rb") as f:
        assert f.read() == b"icon data"


def test_copy_name_collision(tmp_path):
    src = tmp_path / "source" / "icon.png"
    src.parent.mkdir()
    src.write_bytes(b"new data")
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    (dest_dir / "icon.png").write_bytes(b"existing data")

    result = _copy_with_collision_handling(str(src), str(dest_dir))
    assert os.path.basename(result) == "icon_1.png"
    assert os.path.exists(result)


def test_copy_multiple_collisions(tmp_path):
    src = tmp_path / "source" / "icon.png"
    src.parent.mkdir()
    src.write_bytes(b"newest data")
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    (dest_dir / "icon.png").write_bytes(b"v1")
    (dest_dir / "icon_1.png").write_bytes(b"v2")

    result = _copy_with_collision_handling(str(src), str(dest_dir))
    assert os.path.basename(result) == "icon_2.png"


def test_copy_src_in_dest_renames(tmp_path):
    """When src is already in dest_dir, existing file triggers collision rename."""
    f = tmp_path / "icon.png"
    f.write_bytes(b"data")
    result = _copy_with_collision_handling(str(f), str(tmp_path))
    assert os.path.basename(result) == "icon_1.png"
    assert os.path.exists(result)


# ── _normalize_icon_path ────────────────────────────────────────────────────


def test_normalize_inside_user_icons(tmp_path, monkeypatch):
    config_dir = str(tmp_path / "config")
    user_icons_dir = os.path.join(config_dir, "user_icons")
    os.makedirs(user_icons_dir, exist_ok=True)
    monkeypatch.setattr("src.core.config.USER_ICONS_DIR", user_icons_dir)
    monkeypatch.setattr("src.core.config.CONFIG_DIR", config_dir)

    abs_path = os.path.join(user_icons_dir, "test.png")
    result = _normalize_icon_path(abs_path)
    assert result == "user_icons/test.png"


def test_normalize_outside_user_icons(tmp_path, monkeypatch):
    user_icons_dir = str(tmp_path / "config" / "user_icons")
    monkeypatch.setattr("src.core.config.USER_ICONS_DIR", user_icons_dir)
    monkeypatch.setattr("src.core.config.CONFIG_DIR", str(tmp_path / "config"))

    external_path = str(tmp_path / "external" / "icon.png")
    assert _normalize_icon_path(external_path) == external_path


def test_normalize_backslash_conversion(tmp_path, monkeypatch):
    config_dir = str(tmp_path / "config")
    user_icons_dir = os.path.join(config_dir, "user_icons")
    os.makedirs(user_icons_dir, exist_ok=True)
    monkeypatch.setattr("src.core.config.USER_ICONS_DIR", user_icons_dir)
    monkeypatch.setattr("src.core.config.CONFIG_DIR", config_dir)

    abs_path = os.path.join(user_icons_dir, "sub", "test.png")
    result = _normalize_icon_path(abs_path)
    assert "\\" not in result  # All forward slashes on Windows


# ── _icon_path_to_abs ───────────────────────────────────────────────────────


def test_to_abs_user_icons_relative(tmp_path, monkeypatch):
    config_dir = str(tmp_path / "config")
    monkeypatch.setattr("src.core.config.CONFIG_DIR", config_dir)

    result = _icon_path_to_abs("user_icons/foo.png")
    expected = os.path.abspath(os.path.join(config_dir, "user_icons/foo.png"))
    assert result == expected


def test_to_abs_already_absolute(monkeypatch):
    monkeypatch.setattr("src.core.config.CONFIG_DIR", "C:/fake")
    abs_path = os.path.abspath("C:/icons/foo.png")
    assert _icon_path_to_abs(abs_path) == abs_path


def test_to_abs_non_user_icons_relative(monkeypatch):
    monkeypatch.setattr("src.core.config.CONFIG_DIR", "C:/fake")
    result = _icon_path_to_abs("icons/foo.svg")
    assert os.path.isabs(result)
    assert result == os.path.abspath("icons/foo.svg")


# ── _validate_setting_type ──────────────────────────────────────────────────


def test_validate_bool_matches_bool():
    assert _validate_setting_type(True, False) is True


def test_validate_int_matches_int():
    assert _validate_setting_type(42, 0) is True


def test_validate_int_rejected_for_bool_default():
    """int must NOT match bool default (bool is subclass of int in Python)."""
    assert _validate_setting_type(1, True) is False


def test_validate_bool_rejected_for_int_default():
    """bool must NOT match int default."""
    assert _validate_setting_type(True, 0) is False


def test_validate_str_matches_str():
    assert _validate_setting_type("hello", "") is True


def test_validate_str_rejected_for_int():
    assert _validate_setting_type("hello", 0) is False


def test_validate_dict_matches_dict():
    assert _validate_setting_type({"a": 1}, {}) is True


def test_validate_list_matches_list():
    assert _validate_setting_type([1, 2], []) is True


# ── add_to_icon_history ─────────────────────────────────────────────────────


@pytest.fixture()
def icon_env(tmp_path, monkeypatch):
    """Set up isolated icon history environment."""
    config_dir = str(tmp_path / "config")
    user_icons_dir = os.path.join(config_dir, "user_icons")
    history_file = os.path.join(config_dir, "icon_history.json")
    os.makedirs(user_icons_dir, exist_ok=True)

    monkeypatch.setattr("src.core.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("src.core.config.USER_ICONS_DIR", user_icons_dir)
    monkeypatch.setattr("src.core.config.ICON_HISTORY_FILE", history_file)

    return tmp_path, config_dir, user_icons_dir


def test_add_external_copies_to_user_icons(icon_env):
    tmp_path, _, user_icons_dir = icon_env
    src = tmp_path / "external_icon.png"
    src.write_bytes(b"icon data")

    result = add_to_icon_history(str(src))
    assert len(result) == 1
    assert result[0].startswith("user_icons/")
    # Verify file was actually copied
    copied = os.path.join(os.path.dirname(user_icons_dir), result[0].replace("/", os.sep))
    assert os.path.exists(copied)


def test_add_duplicate_reuses_existing(icon_env):
    tmp_path, _, user_icons_dir = icon_env
    content = b"same content"
    (tmp_path / "icon_a.png").write_bytes(content)
    (tmp_path / "icon_b.png").write_bytes(content)

    add_to_icon_history(str(tmp_path / "icon_a.png"))
    # Only one file should exist in user_icons
    files_before = os.listdir(user_icons_dir)

    add_to_icon_history(str(tmp_path / "icon_b.png"))
    files_after = os.listdir(user_icons_dir)
    assert len(files_after) == len(files_before)  # No new file created


def test_add_deduplicates_history(icon_env):
    tmp_path, _, _ = icon_env
    src = tmp_path / "icon.png"
    src.write_bytes(b"data")

    add_to_icon_history(str(src))
    result = add_to_icon_history(str(src))
    assert len(result) == 1  # No duplicates


def test_add_nonexistent_returns_current(icon_env):
    result = add_to_icon_history("/nonexistent/path/icon.png")
    assert isinstance(result, list)
