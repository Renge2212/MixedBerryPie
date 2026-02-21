from unittest.mock import MagicMock, patch

import pytest

from src.core.config import AppSettings, MenuProfile
from src.ui.settings_ui import KeySequenceEdit, SettingsWindow

# qapp fixture is provided by conftest.py


@pytest.fixture
def settings_ui_setup(qapp):
    """Fixture to provide a SettingsWindow instance with mocks"""
    callback = MagicMock()

    # Patch QMessageBox to prevent blocking calls
    with (
        patch("src.ui.settings_ui.QMessageBox") as mock_msgbox,
        patch("src.core.config.load_config") as mock_load,
    ):
        # Default mock data
        settings = AppSettings(replay_unselected=False, long_press_delay_ms=500)
        profile = MenuProfile(name="Test", trigger_key="tab", items=[])
        mock_load.return_value = ([profile], settings)

        window = SettingsWindow(callback)

        yield window, profile, settings, callback, mock_msgbox

        window.close()
        window.deleteLater()


def test_load_data_populates_ui(settings_ui_setup):
    """Test that load_data correctly fills UI elements from settings"""
    window, _, _, _, _ = settings_ui_setup
    assert window.replay_checkbox.isChecked() is False
    assert window.long_press_spin.value() == 500


def test_save_all_updates_settings_from_ui(settings_ui_setup):
    """Test that save_all captures UI changes back into the settings molecule"""
    window, profile, _, _, _ = settings_ui_setup

    window.replay_checkbox.setChecked(True)
    window.long_press_spin.setValue(1000)
    # Ensure trigger key is set to avoid validation block
    profile.trigger_key = "tab"

    with patch("src.core.config.save_config") as mock_save:
        mock_save.return_value = True
        window.save_all()

        # Verify the settings object passed to save_config was updated
        saved_settings = mock_save.call_args[0][1]
        assert saved_settings.replay_unselected is True
        assert saved_settings.long_press_delay_ms == 1000


def test_dirty_flag_on_change(settings_ui_setup):
    """Test that the is_dirty flag is set when UI elements are touched"""
    window, _, _, _, _ = settings_ui_setup

    assert window.is_dirty is False
    window.replay_checkbox.setChecked(not window.replay_checkbox.isChecked())
    assert window.is_dirty is True


def test_key_sequence_edit_mode_switching(qapp):
    """Test switching betweeen key recording and text input modes"""
    edit = KeySequenceEdit()

    # Default mode is "key"
    assert edit.mode == "key"

    # Switch to text mode
    edit.setMode("text")
    assert edit.mode == "text"
    assert edit.isReadOnly() is False

    # Switch back to key mode
    edit.setMode("key")
    assert edit.mode == "key"


def test_key_sequence_edit_recording_disabled_in_text_mode(qapp):
    """Test that recording cannot be enabled in text mode"""
    edit = KeySequenceEdit()
    edit.setMode("text")

    edit.setIsRecording(True)
    assert edit.recording is False


def test_target_apps_tags_ui(settings_ui_setup):
    """Test adding and removing app tags in the UI."""
    window, profile, _, _, _ = settings_ui_setup

    # Switch to the profile to ensure UI is updated
    window.switch_profile(0)
    assert window.current_profile_idx == 0
    assert window.profiles[0] is profile

    # Initially 0 tags
    assert len(profile.target_apps) == 0
    initial_count = window.target_apps_layout.count()

    # Add a tag
    window._add_app_tag("notepad.exe")
    assert "notepad.exe" in profile.target_apps
    assert window.target_apps_layout.count() == initial_count + 1

    # Remove the tag
    window._on_app_tag_removed("notepad.exe")

    assert "notepad.exe" not in profile.target_apps
    assert window.target_apps_layout.count() == initial_count
