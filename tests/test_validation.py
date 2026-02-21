from unittest.mock import MagicMock, patch

import pytest

from src.core.config import AppSettings, MenuProfile
from src.ui.settings_ui import ItemEditorDialog, SettingsWindow

# qapp fixture is provided by conftest.py


@pytest.fixture
def validation_setup(qapp):
    """Fixture for ItemEditorDialog tests"""
    with patch("src.ui.settings_ui.QMessageBox") as mock_msgbox:
        dialog = ItemEditorDialog(trigger_key="tab")
        yield dialog, mock_msgbox
        dialog.close()
        dialog.deleteLater()


def test_conflict_trigger_key(validation_setup):
    """Test that setting action key same as trigger key shows warning"""
    dialog, mock_msgbox = validation_setup

    dialog.label_edit.setText("Test Item")
    # Set action type to 'key'
    index = dialog.action_type_combo.findText("key")
    dialog.action_type_combo.setCurrentIndex(index)

    # Set key to trigger key 'tab' (case insensitive check)
    dialog.key_edit.setText("Tab")

    # Call save
    dialog.save()

    # Verify warning was shown
    mock_msgbox.warning.assert_called()
    args, _ = mock_msgbox.warning.call_args

    expected_text_en = "Cannot set the same key"
    expected_text_ja = "グローバルトリガーキーと同じキーは設定できません"

    # Check if any argument contains expected text
    found = any(expected_text_en in str(arg) or expected_text_ja in str(arg) for arg in args)

    assert found, f"Expected warning text not found in QMessageBox arguments: {args}"


def test_no_conflict_different_key(validation_setup):
    """Test that setting a different key allows saving"""
    dialog, mock_msgbox = validation_setup

    dialog.label_edit.setText("Test Item")
    index = dialog.action_type_combo.findText("key")
    dialog.action_type_combo.setCurrentIndex(index)
    dialog.key_edit.setText("a")

    # Mock accept to verify it's called
    dialog.accept = MagicMock()

    dialog.save()

    # Verify warning was NOT shown
    mock_msgbox.warning.assert_not_called()
    dialog.accept.assert_called_once()


def test_settings_validation_empty_trigger(qapp):
    """Test that SettingsWindow prevents saving if a profile has no trigger key"""
    with (
        patch("src.ui.settings_ui.QMessageBox") as mock_msgbox,
        patch("src.core.config.load_config") as mock_load,
    ):
        # Setup data: One profile has empty trigger
        p1 = MenuProfile(name="Empty", trigger_key="", items=[])
        mock_load.return_value = ([p1], AppSettings())

        window = SettingsWindow(on_save_callback=lambda: None)

        # Try to save
        result = window._save_internal()

        assert result is False
        mock_msgbox.warning.assert_called()
        assert "トリガーキーが空です" in str(mock_msgbox.warning.call_args)


def test_settings_validation_duplicate_trigger(qapp):
    """Test that SettingsWindow prevents saving if two profiles share the same trigger key"""
    with (
        patch("src.ui.settings_ui.QMessageBox") as mock_msgbox,
        patch("src.core.config.load_config") as mock_load,
    ):
        # Setup data: Two profiles with same trigger
        p1 = MenuProfile(name="P1", trigger_key="tab", items=[])
        p2 = MenuProfile(name="P2", trigger_key="tab", items=[])
        mock_load.return_value = ([p1, p2], AppSettings())

        window = SettingsWindow(on_save_callback=lambda: None)

        # Try to save
        result = window._save_internal()

        assert result is False
        mock_msgbox.warning.assert_called()
        assert "重複しないように設定してください" in str(mock_msgbox.warning.call_args)
