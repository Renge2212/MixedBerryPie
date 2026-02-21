from unittest.mock import MagicMock, patch

import pytest

from src.app import MixedBerryPieApp
from src.core.config import AppSettings, MenuProfile

# qapp fixture is provided by conftest.py

@pytest.fixture
def onboarding_setup(qapp):
    """Fixture to provide mocks and setup for onboarding tests"""
    with patch('src.app.QSystemTrayIcon'), \
         patch('src.app.HookManager'), \
         patch('src.app.PieOverlay'), \
         patch('src.core.config.load_config') as mock_load, \
         patch('src.app.QTimer') as mock_timer:

        mock_p = MagicMock(spec=MenuProfile)
        mock_p.trigger_key = "ctrl+space"
        mock_profiles = [mock_p]
        mock_settings = AppSettings()

        yield mock_load, mock_timer, mock_profiles, mock_settings

def test_first_run_triggers_timer(onboarding_setup):
    """Test that first run triggers a singleShot timer to show welcome dialog."""
    mock_load, mock_timer, mock_profiles, mock_settings = onboarding_setup

    # Setup first_run = True
    mock_settings.first_run = True
    mock_load.return_value = (mock_profiles, mock_settings)

    app = MixedBerryPieApp()

    # Verify singleShot was called with 1000ms and app.show_welcome_dialog
    mock_timer.singleShot.assert_called_with(1000, app.show_welcome_dialog)

def test_subsequent_run_does_not_trigger_timer(onboarding_setup):
    """Test that subsequent runs do NOT trigger the welcome dialog timer."""
    mock_load, mock_timer, mock_profiles, mock_settings = onboarding_setup

    # Setup first_run = False
    mock_settings.first_run = False
    mock_load.return_value = (mock_profiles, mock_settings)

    app = MixedBerryPieApp()

    # Verify singleShot was NOT called for welcome dialog
    for call_args in mock_timer.singleShot.call_args_list:
        args, _ = call_args
        if args[1] == app.show_welcome_dialog:
            pytest.fail("QTimer.singleShot called with show_welcome_dialog when first_run is False")

@patch('src.core.config.save_config')
@patch('src.app.WelcomeDialog')
def test_show_welcome_dialog_logic(mock_dialog_cls, mock_save, onboarding_setup):
    """Test show_welcome_dialog execution path."""
    mock_load, _, mock_profiles, mock_settings = onboarding_setup

    mock_settings.first_run = True
    mock_load.return_value = (mock_profiles, mock_settings)

    app = MixedBerryPieApp()

    # Mock dialog instance
    mock_dialog_instance = mock_dialog_cls.return_value

    # Call the method
    app.show_welcome_dialog()

    # assert dialog created and exec called
    mock_dialog_cls.assert_called_once()
    mock_dialog_instance.exec.assert_called_once()

    # assert first_run set to False
    assert not mock_settings.first_run

    # assert config saved
    mock_save.assert_called_once_with(mock_profiles, mock_settings)
