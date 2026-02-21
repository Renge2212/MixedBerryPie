"""Tests for HookManager (pynput-based implementation with win32_event_filter)."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from pynput import keyboard as pynput_keyboard

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.hook_manager import HookManager, _parse_key

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_manager(release_return=False):
    press_cb = MagicMock(return_value=None)
    release_cb = MagicMock(return_value=release_return)
    mgr = HookManager(on_trigger_press=press_cb, on_trigger_release=release_cb)
    return mgr, press_cb, release_cb


def make_data(vk: int):
    """Create a mock KBDLLHOOKSTRUCT-like object."""
    d = MagicMock()
    d.vkCode = vk
    return d


WM_KEYDOWN = 0x100
WM_KEYUP = 0x101
WM_SYSKEYDOWN = 0x104
WM_SYSKEYUP = 0x105

VK_SPACE = 0x20
VK_CTRL_L = 0xA2
VK_CTRL_R = 0xA3
VK_ALT_L = 0xA4
VK_SHIFT_L = 0xA0
VK_TAB = 0x09


# ── Initialization ────────────────────────────────────────────────────────────


def test_initialization():
    mgr, _, _ = make_manager()
    assert mgr._trigger_configs == {}
    assert mgr._active_suppressions == {}
    assert mgr._held_modifiers == set()


# ── start_hook ────────────────────────────────────────────────────────────────


def test_start_hook_simple_key():
    mgr, _, _ = make_manager()
    with patch.object(mgr, "_start_listener"):
        mgr.start_hook(["tab"])
    assert "tab" in mgr._trigger_configs
    modifiers, full_key = mgr._trigger_configs["tab"][0]
    assert modifiers == ()
    assert full_key == "tab"


def test_start_hook_with_modifiers():
    mgr, _, _ = make_manager()
    with patch.object(mgr, "_start_listener"):
        mgr.start_hook(["ctrl+shift+space"])
    assert "space" in mgr._trigger_configs
    modifiers, full_key = mgr._trigger_configs["space"][0]
    assert sorted(modifiers) == ["ctrl", "shift"]
    assert full_key == "ctrl+shift+space"


def test_start_hook_multiple_profiles_same_primary():
    mgr, _, _ = make_manager()
    with patch.object(mgr, "_start_listener"):
        mgr.start_hook(["ctrl+tab", "shift+tab"])
    assert "tab" in mgr._trigger_configs
    assert len(mgr._trigger_configs["tab"]) == 2


# ── stop_hook ─────────────────────────────────────────────────────────────────


def test_stop_hook_clears_state():
    mgr, _, _ = make_manager()
    with patch.object(mgr, "_start_listener"):
        mgr.start_hook(["tab"])
    mgr._active_suppressions["tab"] = "tab"
    mgr._held_modifiers.add("ctrl")

    with patch.object(mgr, "_stop_listener_unsafe"):
        mgr.stop_hook()

    assert mgr._active_suppressions == {}
    assert mgr._held_modifiers == set()


# ── win32_event_filter: modifier tracking ─────────────────────────────────────


def test_filter_tracks_ctrl_press():
    mgr, _, _ = make_manager()
    mgr._listener = MagicMock()
    mgr._win32_event_filter(WM_KEYDOWN, make_data(VK_CTRL_L))
    assert "ctrl" in mgr._held_modifiers


def test_filter_tracks_ctrl_release():
    mgr, _, _ = make_manager()
    mgr._listener = MagicMock()
    mgr._held_modifiers.add("ctrl")
    mgr._win32_event_filter(WM_KEYUP, make_data(VK_CTRL_L))
    assert "ctrl" not in mgr._held_modifiers


def test_filter_passes_modifier_through():
    mgr, _, _ = make_manager()
    mgr._listener = MagicMock()
    result = mgr._win32_event_filter(WM_KEYDOWN, make_data(VK_CTRL_L))
    assert result is True
    mgr._listener.suppress_event.assert_not_called()


# ── win32_event_filter: trigger press ─────────────────────────────────────────


def test_filter_suppresses_and_fires_press_callback():
    mgr, _press_cb, _ = make_manager()
    with patch.object(mgr, "_start_listener"):
        mgr.start_hook(["ctrl+space"])
    mgr._listener = MagicMock()  # set AFTER start_hook

    mgr._held_modifiers = {"ctrl"}
    with patch("threading.Thread") as mock_thread:
        result = mgr._win32_event_filter(WM_KEYDOWN, make_data(VK_SPACE))

    assert result is False
    assert "space" in mgr._active_suppressions
    mock_thread.assert_called_once()


def test_filter_no_suppress_wrong_modifiers():
    mgr, _press_cb, _ = make_manager()
    with patch.object(mgr, "_start_listener"):
        mgr.start_hook(["ctrl+space"])
    mgr._listener = MagicMock()  # set AFTER start_hook

    mgr._held_modifiers = set()  # ctrl not held
    result = mgr._win32_event_filter(WM_KEYDOWN, make_data(VK_SPACE))

    assert result is True
    mgr._listener.suppress_event.assert_not_called()
    assert "space" not in mgr._active_suppressions


# ── win32_event_filter: trigger release ──────────────────────────────────────


def test_filter_suppresses_release_and_fires_release_callback():
    mgr, _, _release_cb = make_manager(release_return=True)
    mgr._listener = MagicMock()
    mgr._active_suppressions["space"] = "ctrl+space"

    with patch("threading.Thread") as mock_thread:
        result = mgr._win32_event_filter(WM_KEYUP, make_data(VK_SPACE))

    assert result is False
    assert "space" not in mgr._active_suppressions
    mock_thread.assert_called_once()


def test_filter_passes_unsuppressed_release_through():
    mgr, _, _ = make_manager()
    mgr._listener = MagicMock()
    # space is NOT in _active_suppressions
    result = mgr._win32_event_filter(WM_KEYUP, make_data(VK_SPACE))
    assert result is True
    mgr._listener.suppress_event.assert_not_called()


# ── _handle_release ───────────────────────────────────────────────────────────


def test_handle_release_consumed_no_replay():
    mgr, _, release_cb = make_manager(release_return=True)
    with patch.object(mgr, "_replay_key") as mock_replay:
        mgr._handle_release("ctrl+space", "space")
    release_cb.assert_called_once_with("ctrl+space")
    mock_replay.assert_not_called()


def test_handle_release_not_consumed_replays():
    mgr, _, _release_cb = make_manager(release_return=False)
    with patch.object(mgr, "_replay_key") as mock_replay:
        mgr._handle_release("space", "space")
    mock_replay.assert_called_once_with("space")


# ── release_all_modifiers ─────────────────────────────────────────────────────


def test_release_all_modifiers():
    mgr, _, _ = make_manager()
    mgr._held_modifiers = {"ctrl", "shift"}
    with patch("src.core.win32_input.send_pynput_key_safely") as mock_release:
        mgr.release_all_modifiers()
    assert mock_release.call_count == 2


# ── _parse_key ────────────────────────────────────────────────────────────────


def test_parse_key_space():
    assert _parse_key("space") == pynput_keyboard.Key.space


def test_parse_key_char():
    key = _parse_key("p")
    assert hasattr(key, "char") and key.char == "p"


def test_parse_key_f5():
    assert _parse_key("f5") == pynput_keyboard.Key.f5


# ── multi-profile same primary ────────────────────────────────────────────────


def test_filter_ctrl_tab_vs_shift_tab():
    mgr, _press_cb, _ = make_manager()
    with patch.object(mgr, "_start_listener"):
        mgr.start_hook(["ctrl+tab", "shift+tab"])
    mgr._listener = MagicMock()  # set AFTER start_hook

    # ctrl+tab
    mgr._held_modifiers = {"ctrl"}
    with patch("threading.Thread"):
        mgr._win32_event_filter(WM_KEYDOWN, make_data(VK_TAB))
    assert mgr._active_suppressions.get("tab") == "ctrl+tab"

    # Reset
    mgr._active_suppressions.clear()
    mgr._listener.reset_mock()

    # shift+tab
    mgr._held_modifiers = {"shift"}
    with patch("threading.Thread"):
        mgr._win32_event_filter(WM_KEYDOWN, make_data(VK_TAB))
    assert mgr._active_suppressions.get("tab") == "shift+tab"


# ── _NativeWin32Hook (Windows Only) ───────────────────────────────────────────


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_native_hook_ignores_injected():
    import ctypes

    from src.core.hook_manager import HC_ACTION, KBDLLHOOKSTRUCT, _NativeWin32Hook
    from src.core.win32_input import MAGIC_EXTRA_INFO

    # Mock filter function to always suppress (return False)
    mock_filter = MagicMock(return_value=False)
    hook = _NativeWin32Hook(mock_filter)
    hook.hook_id = 999  # Dummy hook ID

    # Create an injected kb_struct (dwExtraInfo == MAGIC_EXTRA_INFO)
    kb_struct = KBDLLHOOKSTRUCT()
    kb_struct.vkCode = 0x41  # 'A'
    kb_struct.dwExtraInfo = MAGIC_EXTRA_INFO

    l_param = ctypes.cast(ctypes.pointer(kb_struct), ctypes.c_void_p).value

    # We must patch CallNextHookEx so we don't actually call the real Windows API
    with patch("ctypes.windll.user32.CallNextHookEx", return_value=123) as mock_callnext:
        result = hook._hook_callback(HC_ACTION, WM_KEYDOWN, l_param)

    # Since it's our own event, it should NOT have called filter_func
    mock_filter.assert_not_called()
    # It should have passed it onto the next hook
    mock_callnext.assert_called_once_with(999, HC_ACTION, WM_KEYDOWN, l_param)
    assert result == 123


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_native_hook_suppresses_on_false():
    import ctypes

    from src.core.hook_manager import HC_ACTION, KBDLLHOOKSTRUCT, _NativeWin32Hook

    # Mock filter function to suppress (return False)
    mock_filter = MagicMock(return_value=False)
    hook = _NativeWin32Hook(mock_filter)

    # Create normal kb_struct (flags = 0)
    kb_struct = KBDLLHOOKSTRUCT()
    kb_struct.vkCode = 0x41
    kb_struct.flags = 0

    l_param = ctypes.cast(ctypes.pointer(kb_struct), ctypes.c_void_p).value

    with patch("ctypes.windll.user32.CallNextHookEx") as mock_callnext:
        result = hook._hook_callback(HC_ACTION, WM_KEYDOWN, l_param)

    # Should have called the filter
    mock_filter.assert_called_once()
    # It returned False -> hook_callback returns 1 (suppressed)
    assert result == 1
    mock_callnext.assert_not_called()


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_native_hook_passes_on_true():
    import ctypes

    from src.core.hook_manager import HC_ACTION, KBDLLHOOKSTRUCT, _NativeWin32Hook

    # Mock filter function to pass through (return True)
    mock_filter = MagicMock(return_value=True)
    hook = _NativeWin32Hook(mock_filter)
    hook.hook_id = 888

    kb_struct = KBDLLHOOKSTRUCT()
    kb_struct.flags = 0

    l_param = ctypes.cast(ctypes.pointer(kb_struct), ctypes.c_void_p).value

    with patch("ctypes.windll.user32.CallNextHookEx", return_value=456) as mock_callnext:
        result = hook._hook_callback(HC_ACTION, WM_KEYDOWN, l_param)

    mock_filter.assert_called_once()
    # It returned True -> passes to CallNextHookEx
    mock_callnext.assert_called_once()
    assert result == 456
