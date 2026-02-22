import atexit
import os
import shlex
import signal
import subprocess
import sys
import time
import webbrowser
from typing import Any, cast

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from src.core import config, i18n
from src.core.config import MenuProfile
from src.core.hook_manager import HookManager, _parse_key
from src.core.logger import LOGS_DIR, get_logger
from src.core.utils import get_resource_path
from src.core.version import __version__
from src.core.win32_input import get_active_window_info, send_pynput_key_safely
from src.ui.help_dialog import HelpDialog
from src.ui.overlay import PieOverlay
from src.ui.settings_ui import SettingsWindow
from src.ui.welcome_dialog import WelcomeDialog

# Use a unique name to avoid shadowing/scoping issues
app_logger = get_logger("piemenu.app")


class KeySignal(QObject):
    """Signal definition for key events."""

    show_signal = pyqtSignal()
    hide_signal = pyqtSignal(bool)  # bool: execute action?
    timer_start_signal = pyqtSignal(int)
    timer_stop_signal = pyqtSignal()
    do_show_signal = pyqtSignal(object)  # object: profile


class MixedBerryPieApp(QObject):
    """Main application logic for MixedBerryPie.

    Handles system tray, global hotkeys, menu overlay, and settings.
    """

    def __init__(self) -> None:
        """Initialize the application."""
        super().__init__()
        app_logger.info(f"Initializing MixedBerryPie Application v{__version__}")
        app_instance = QApplication.instance()
        if app_instance is None:
            self.app = QApplication(sys.argv)
        else:
            self.app = cast(QApplication, app_instance)
        QApplication.setQuitOnLastWindowClosed(False)  # Keep app running even if window is hidden
        self.app.setApplicationName("MixedBerryPie")
        self.app.setApplicationVersion(__version__)

        # Config
        self.profiles, self.settings = config.load_config()
        app_logger.info(f"Loaded {len(self.profiles)} menu profiles")

        # Initialize translator
        i18n.install_translator(self.app, self.settings.language)

        # Components
        # We start with empty items, will populate on-the-fly when triggered
        self.overlay = PieOverlay([], self.settings)
        self.settings_window: SettingsWindow | None = None
        self.hook_manager = HookManager(
            on_trigger_press=self.on_trigger_press, on_trigger_release=self.on_trigger_release
        )

        # Long press support
        self.long_press_timer = QTimer(self)
        self.long_press_timer.setSingleShot(True)
        self.long_press_timer.timeout.connect(self._show_overlay_after_delay)
        self.pending_profile: MenuProfile | None = None

        self.setup_tray()
        self.setup_signals()
        self.setup_shutdown_handlers()

        self.is_menu_visible = False

        # Start Hook for all profiles
        trigger_keys = [p.trigger_key for p in self.profiles]
        self.hook_manager.start_hook(trigger_keys)
        app_logger.info("Application initialized successfully")

        # Check for first run
        app_logger.info(f"Checking first_run flag: {self.settings.first_run}")
        if self.settings.first_run:
            app_logger.info("Scheduling Welcome Dialog in 1000ms")
            QTimer.singleShot(1000, self.show_welcome_dialog)
        else:
            app_logger.info("Not first run, skipping Welcome Dialog")

    def show_welcome_dialog(self) -> None:
        """Show the welcome dialog and update first_run flag."""
        app_logger.info("First run detected, showing welcome dialog")
        dialog = WelcomeDialog()
        dialog.exec()

        # Update flag
        self.settings.first_run = False
        config.save_config(self.profiles, self.settings)

    def setup_shutdown_handlers(self) -> None:
        """Setup graceful shutdown handlers for signals and exit."""
        app_logger.info("Setting up shutdown handlers")

        # Register atexit handler
        atexit.register(self.cleanup)

        # Register signal handlers (SIGINT, SIGTERM)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        app_logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.exit_app()

    def setup_signals(self) -> None:
        """Connect internal signals for cross-thread communication."""
        # Cross-thread signals for showing/hiding overlay from hook thread
        self.key_signal = KeySignal()
        self.key_signal.show_signal.connect(  # type: ignore
            self.overlay.show_menu, Qt.ConnectionType.QueuedConnection
        )
        self.key_signal.hide_signal.connect(  # type: ignore
            self.overlay.hide_menu, Qt.ConnectionType.QueuedConnection
        )
        self.key_signal.timer_start_signal.connect(  # type: ignore
            self.long_press_timer.start, Qt.ConnectionType.QueuedConnection
        )
        self.key_signal.timer_stop_signal.connect(  # type: ignore
            self.long_press_timer.stop, Qt.ConnectionType.QueuedConnection
        )
        self.key_signal.do_show_signal.connect(  # type: ignore
            self._do_show_overlay, Qt.ConnectionType.QueuedConnection
        )

        # Connect Overlay action signal to execution
        self.overlay.action_selected.connect(self.execute_action)

    def setup_tray(self) -> None:
        """Initialize and display the system tray icon."""
        app_logger.debug("Setting up system tray icon")
        self.tray_icon = QSystemTrayIcon(self.app)

        icon_path = get_resource_path(os.path.join("resources", "app_icon.ico"))
        self.tray_icon.setIcon(QIcon(icon_path))

        # Context Menu
        menu = QMenu()

        # Add version to menu title
        title_action = menu.addAction(f"MixedBerryPie v{__version__}")
        if title_action:
            title_action.setEnabled(False)
        menu.addSeparator()

        settings_action = menu.addAction(self.tr("Settings"))
        if settings_action:
            settings_action.triggered.connect(self.open_settings)

        help_action = menu.addAction(self.tr("Help"))
        if help_action:
            help_action.triggered.connect(self.open_help)

        logs_action = menu.addAction(self.tr("View Logs"))
        if logs_action:
            logs_action.triggered.connect(self.open_logs)

        menu.addSeparator()

        exit_action = menu.addAction(self.tr("Exit MixedBerryPie"))
        if exit_action:
            exit_action.triggered.connect(self.exit_app)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def open_settings(self) -> None:
        """Open the settings configuration window."""
        app_logger.info("Opening settings window")
        if not self.settings_window:
            self.settings_window = SettingsWindow(
                on_save_callback=self.save_settings,
                on_suspend_hooks=self.suspend_hooks_for_recording,
                on_resume_hooks=self.resume_hooks_after_recording,
            )
        self.settings_window.show()
        self.settings_window.activateWindow()

    def suspend_hooks_for_recording(self) -> None:
        """Temporarily stop hooks to allow key recording."""
        self.hook_manager.stop_hook()

    def resume_hooks_after_recording(self) -> None:
        """Resume hooks after recording."""
        self.update_hooks()

    def save_settings(self) -> None:
        """Callback from settings window when settings are saved."""
        self.reload_config()
        if self.settings_window:
            self.settings_window.raise_()
            self.settings_window.activateWindow()

    def open_help(self) -> None:
        """Open help dialog."""
        app_logger.info("Opening help dialog")
        help_dialog = HelpDialog(None)
        help_dialog.exec()

    def open_logs(self) -> None:
        """Open the logs directory in file explorer."""
        app_logger.info(f"Opening logs directory: {LOGS_DIR}")
        if os.path.exists(LOGS_DIR):
            os.startfile(LOGS_DIR)
        else:
            app_logger.warning(f"Logs directory does not exist: {LOGS_DIR}")
            QMessageBox.warning(None, "Error", self.tr("Logs directory not found."))

    def update_hooks(self) -> None:
        """Re-calculate and start hooks based on current profiles."""
        triggers = {p.trigger_key for p in self.profiles if p.trigger_key}
        self.hook_manager.start_hook(list(triggers))

    def reload_config(self) -> None:
        """Reload configuration from disk and update components."""
        app_logger.info("Reloading configuration")
        self.profiles, self.settings = config.load_config()
        self.overlay.update_settings(self.settings)
        self.update_hooks()
        app_logger.info("Config reloaded successfully")

    def cleanup(self) -> None:
        """Cleanup resources before exit."""
        app_logger.info("Cleaning up resources")
        try:
            self.hook_manager.unhook_all()
            app_logger.info("Hooks cleaned up successfully")
        except Exception as e:
            app_logger.error(f"Error during cleanup: {e}")

    def exit_app(self) -> None:
        """Terminate the application."""
        app_logger.info("Exiting application")
        self.cleanup()
        self.app.quit()

    def on_trigger_press(self, trigger_key: str) -> None:
        """Handle trigger key press event."""
        app_logger.info(f"App: Trigger press callback for '{trigger_key}'")
        if not self.is_menu_visible and not self.pending_profile:
            active_exe, active_title = get_active_window_info()
            app_logger.debug(f"Active App: {active_exe}, Title: {active_title}")

            matches = [p for p in self.profiles if p.trigger_key == trigger_key]
            if not matches:
                return

            selected_profile: MenuProfile | None = None
            if active_exe:
                for p in matches:
                    if p.target_apps:
                        is_match = False
                        for target in p.target_apps:
                            target = target.lower()
                            if target in active_exe or (
                                active_title and target in active_title.lower()
                            ):
                                is_match = True
                                break
                        if is_match:
                            selected_profile = p
                            break
            if not selected_profile:
                selected_profile = next((p for p in matches if not p.target_apps), None)

            if selected_profile:
                app_logger.info(f"App: Matching profile found: {selected_profile.name}")
                delay = self.settings.long_press_delay_ms
                if delay <= 0:
                    self.key_signal.do_show_signal.emit(selected_profile)
                else:
                    self.pending_profile = selected_profile
                    self.key_signal.timer_start_signal.emit(delay)

    def _show_overlay_after_delay(self) -> None:
        """Called by QTimer after long press delay."""
        if self.pending_profile:
            app_logger.debug(f"Long press delay met, showing profile: {self.pending_profile.name}")
            self._do_show_overlay(self.pending_profile)
            self.pending_profile = None

    def _do_show_overlay(self, profile: MenuProfile) -> None:
        """Actually show the overlay."""
        app_logger.info(f"App: _do_show_overlay called for profile: {profile.name}")
        self.overlay.menu_items = profile.items
        self.is_menu_visible = True
        self.key_signal.show_signal.emit()

    def on_trigger_release(self, trigger_key: str) -> bool:
        """Handle trigger key release."""
        self.key_signal.timer_stop_signal.emit()
        if self.pending_profile:
            app_logger.debug(f"Trigger {trigger_key} released BEFORE long press delay")
            self.pending_profile = None
            return not self.settings.replay_unselected

        if self.is_menu_visible:
            was_selected = self.overlay.selected_index != -1
            app_logger.debug(f"Trigger {trigger_key} released, item selected: {was_selected}")
            self.is_menu_visible = False
            self.key_signal.hide_signal.emit(True)
            if was_selected:
                return True
            else:
                return not self.settings.replay_unselected
        return False

    def execute_action(self, item_key: str, action_type: str = "key") -> None:
        """Execute the selected action after a brief delay."""
        app_logger.info(f"Queuing action: {item_key} (type: {action_type})")
        delay_ms = self.settings.action_delay_ms
        QTimer.singleShot(delay_ms, lambda: self._do_execute(item_key, action_type))

    def _do_execute(self, value: str, action_type: str) -> None:
        """Internal method to execute actions."""
        app_logger.info(f"Executing action: {value} ({action_type})")
        try:
            if action_type == "url":
                webbrowser.open(value)
            elif action_type == "cmd":
                args = shlex.split(value)
                subprocess.Popen(args, shell=False)
            else:
                # Release modifiers to prevent leakage
                self.hook_manager.release_all_modifiers()

                parts = value.lower().split("+")
                keys_to_press = [_parse_key(p) for p in parts]
                app_logger.debug(f"Sending keys: {parts} (parsed: {keys_to_press})")

                # Sequential key handling with safety delays
                delay_sec = getattr(self.settings, "key_sequence_delay_ms", 0) / 1000.0
                for k in keys_to_press:
                    send_pynput_key_safely(k, True)
                    if delay_sec > 0:
                        time.sleep(delay_sec)
                for k in reversed(keys_to_press):
                    send_pynput_key_safely(k, False)
                    if delay_sec > 0:
                        time.sleep(delay_sec)
                if delay_sec > 0:
                    time.sleep(delay_sec)

            app_logger.info(f"Action executed successfully: {value}")
        except Exception as e:
            error_msg = f"Failed to execute action '{value}': {e!s}"
            app_logger.error(error_msg)
            QMessageBox.warning(None, "Action Execution Error", error_msg)

    def run(self) -> None:
        """Start the application event loop."""
        app_logger.info("Starting application event loop")
        try:
            return_code = self.app.exec()
            app_logger.info(f"Application exited with code {return_code}")
            sys.exit(return_code)
        except KeyboardInterrupt:
            app_logger.info("KeyboardInterrupt received")
            self.exit_app()
        except Exception as e:
            app_logger.critical(f"Critical error in main loop: {e}", exc_info=True)
            self.exit_app()
        finally:
            try:
                self.hook_manager.unhook_all()
                app_logger.info("Final hook cleanup completed")
            except Exception as e:
                app_logger.error(f"Error in final cleanup: {e}")


if __name__ == "__main__":
    menu = MixedBerryPieApp()
    menu.run()
