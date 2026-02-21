from unittest.mock import MagicMock, call, patch

import pytest

# qapp fixture is provided by conftest.py
from src.core.config import AppSettings, MenuProfile, PieSlice


@pytest.fixture
def app_setup(qapp):
    """Fixture to provide a MixedBerryPieApp instance with mocked dependencies"""
    with patch('src.app.QSystemTrayIcon'), \
         patch('src.app.HookManager'), \
         patch('src.core.config.load_config') as mock_load:

        # Setup mock data
        test_profile = MenuProfile(
            name="Test",
            trigger_key="tab",
            items=[PieSlice("Test", "a", "#ffffff")]
        )
        test_settings = AppSettings()
        mock_load.return_value = ([test_profile], test_settings)

        # Import inside the patched context to ensure decorators/imports work if needed
        # (Though imports are top-level here, patching happens before instantiation)
        from src.app import MixedBerryPieApp

        pie_app = MixedBerryPieApp()

        # Mock the overlay and key_signal
        pie_app.overlay = MagicMock()
        pie_app.key_signal = MagicMock()

        yield pie_app, test_profile, test_settings

def test_instant_show_when_delay_is_zero(app_setup):
    """Test menu emits show signal instantly when long_press_delay_ms is 0"""
    pie_app, test_profile, test_settings = app_setup
    test_settings.long_press_delay_ms = 0

    pie_app.on_trigger_press("tab")

    # Now it goes through do_show_signal
    pie_app.key_signal.do_show_signal.emit.assert_called_once_with(test_profile)

def test_long_press_timer_starts_when_delay_set(app_setup):
    """Test long press timer starts if delay is > 0"""
    pie_app, test_profile, test_settings = app_setup
    test_settings.long_press_delay_ms = 300

    # In a real app, signals are used. We'll check if timer_start_signal was emitted.
    pie_app.on_trigger_press("tab")

    assert pie_app.pending_profile == test_profile
    pie_app.key_signal.timer_start_signal.emit.assert_called_once_with(300)
    # Menu should NOT be visible yet
    assert not pie_app.is_menu_visible

def test_release_before_delay_replays_key_if_enabled(app_setup):
    """Test releasing key before delay replays the key if replay is enabled"""
    pie_app, _, test_settings = app_setup
    test_settings.long_press_delay_ms = 300
    test_settings.replay_unselected = True

    pie_app.on_trigger_press("tab")
    # Simulate release before timer finish
    # pending_profile being set means timer was started but menu not yet shown
    consumed = pie_app.on_trigger_release("tab")

    assert consumed is False # False means replay
    assert pie_app.pending_profile is None
    pie_app.key_signal.timer_stop_signal.emit.assert_called()

def test_release_before_delay_consumes_key_if_replay_disabled(app_setup):
    """Test releasing key before delay consumes key if replay is disabled"""
    pie_app, _, test_settings = app_setup
    test_settings.long_press_delay_ms = 300
    test_settings.replay_unselected = False

    pie_app.on_trigger_press("tab")
    consumed = pie_app.on_trigger_release("tab")

    assert consumed is True # True means do NOTHING (consume)
    assert pie_app.pending_profile is None

def test_release_no_selection_replays_if_enabled(app_setup):
    """Test releasing key with no item selected replays key if enabled"""
    pie_app, _, test_settings = app_setup
    test_settings.replay_unselected = True
    pie_app.is_menu_visible = True
    pie_app.overlay.selected_index = -1

    consumed = pie_app.on_trigger_release("tab")

    assert consumed is False
    assert not pie_app.is_menu_visible
    pie_app.key_signal.hide_signal.emit.assert_called_with(True)

def test_release_no_selection_consumes_if_disabled(app_setup):
    """Test releasing key with no item selected consumes key if disabled"""
    pie_app, _, test_settings = app_setup
    test_settings.replay_unselected = False
    pie_app.is_menu_visible = True
    pie_app.overlay.selected_index = -1

    consumed = pie_app.on_trigger_release("tab")

    assert consumed is True

def test_selection_always_consumes_event(app_setup):
    """Test that event is always consumed if an item was selected"""
    pie_app, _, test_settings = app_setup
    test_settings.replay_unselected = True # Even if replay enabled
    pie_app.is_menu_visible = True
    pie_app.overlay.selected_index = 0

    consumed = pie_app.on_trigger_release("tab")

    assert consumed is True


def test_do_execute_multi_key_shortcut(app_setup):
    """Test that _do_execute correctly parses and sequences multi-key shortcuts (e.g. ctrl+c)"""
    pie_app, _, _ = app_setup

    with patch('src.app.send_pynput_key_safely') as mock_send, \
         patch('src.app._parse_key', side_effect=lambda x: f"mock_key_{x}"):

        pie_app._do_execute("ctrl+c", "key")

        # Verify hook manager was asked to release its tracking modifiers
        pie_app.hook_manager.release_all_modifiers.assert_called_once()

        # Verify the press calls happen in forward order (True for is_press)
        mock_send.assert_has_calls([
            call("mock_key_ctrl", True),
            call("mock_key_c", True),
            # Verify the release calls happen in reverse order (False for is_press)
            call("mock_key_c", False),
            call("mock_key_ctrl", False)
        ])
