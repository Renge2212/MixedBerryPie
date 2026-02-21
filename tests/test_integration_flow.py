from unittest.mock import MagicMock, patch

import pytest

from src.app import MixedBerryPieApp
from src.core.config import AppSettings, MenuProfile
from src.ui.settings_ui import SettingsWindow


@pytest.fixture
def integration_setup(qapp, tmp_path, monkeypatch):
    """Setup app and settings UI with a temporary config file."""
    config_file = tmp_path / "menu_config.json"
    monkeypatch.setattr("src.core.config.CONFIG_FILE", str(config_file))
    monkeypatch.setattr("src.core.config.CONFIG_DIR", str(tmp_path))

    # Initial config
    initial_profiles = [MenuProfile(name="Initial", trigger_key="ctrl+space", items=[])]
    initial_settings = AppSettings(menu_opacity=80)

    from src.core.config import save_config

    save_config(initial_profiles, initial_settings)

    with patch("src.app.QSystemTrayIcon"), patch("src.app.HookManager.start_hook"):
        app = MixedBerryPieApp()
        # Mock overlay to track updates
        app.overlay = MagicMock()
        yield app, config_file


def test_settings_save_reloads_app_config(integration_setup):
    """Verify that saving settings in UI triggers reload in App and updates Overlay."""
    app, _config_file = integration_setup

    # Create settings window (it hooks into app.save_settings)
    window = SettingsWindow(
        on_save_callback=app.save_settings,
        on_suspend_hooks=app.suspend_hooks_for_recording,
        on_resume_hooks=app.resume_hooks_after_recording,
    )

    # Simulate UI change: Update opacity in UI
    window.menu_opacity_slider.setValue(50)

    # Verification before save
    assert app.settings.menu_opacity == 80

    # Trigger save in UI
    # We patch QMessageBox to avoid blocking dialogs
    with patch("src.ui.settings_ui.QMessageBox"):
        window.save_all()

    # 1. Verify file was updated (implicitly verified by reload_config)
    # 2. Verify app.settings was updated
    assert app.settings.menu_opacity == 50

    # 3. Verify overlay.update_settings was called with new settings
    app.overlay.update_settings.assert_called()
    new_settings = app.overlay.update_settings.call_args[0][0]
    assert new_settings.menu_opacity == 50


def test_trigger_key_change_updates_hooks(integration_setup):
    """Verify that changing a trigger key reloads hooks in HookManager."""
    app, _config_file = integration_setup

    window = SettingsWindow(
        on_save_callback=app.save_settings,
        on_suspend_hooks=app.suspend_hooks_for_recording,
        on_resume_hooks=app.resume_hooks_after_recording,
    )

    # Change trigger key for the first profile
    window.trigger_input.setText("f12")

    # Verification before save
    assert app.profiles[0].trigger_key == "ctrl+space"

    with (
        patch("src.ui.settings_ui.QMessageBox"),
        patch.object(app.hook_manager, "start_hook") as mock_start_hook,
    ):
        window.save_all()

        # Verify hook manager was restarted with new trigger
        # reload_config calls update_hooks which calls hook_manager.start_hook
        mock_start_hook.assert_called_with(["f12"])

    assert app.profiles[0].trigger_key == "f12"
