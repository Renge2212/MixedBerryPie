"""Configuration management for PieMenu application.

This module handles loading, saving, and migrating configuration files.
It defines the core data structures (PieSlice, AppSettings, MenuProfile)
and provides functions to persist them to disk.
"""

import json
import os
from dataclasses import asdict, dataclass, field

from src.core.logger import get_logger

logger = get_logger(__name__)

# Project root resolution
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Config Path Resolution (AppData)
APP_NAME = "MixedBerryPie"
APPDATA = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
CONFIG_DIR = os.path.join(APPDATA, APP_NAME)
CONFIG_FILE = os.path.join(CONFIG_DIR, "menu_config.json")

# Legacy Config Path (for migration)
LEGACY_CONFIG_FILE = os.path.join(PROJECT_ROOT, "menu_config.json")


def _ensure_config_dir() -> None:
    """Ensure the configuration directory exists.

    Creates the config directory if it doesn't exist.
    Logs success or failure.
    """
    if not os.path.exists(CONFIG_DIR):
        try:
            os.makedirs(CONFIG_DIR)
            logger.info(f"Created config directory: {CONFIG_DIR}")
        except Exception as e:
            logger.error(f"Failed to create config directory: {e}")


@dataclass
class PieSlice:
    """Represents a single item in the pie menu.

    Attributes:
        label: Display text for the menu item
        key: Keyboard shortcut or action value
        color: Hex color code for the item (e.g., '#FF5555')
        action_type: Type of action ('key', 'url', or 'cmd')
        icon_path: Optional path to an icon file
    """

    label: str
    key: str
    color: str
    action_type: str = "key"  # 'key', 'url', 'cmd'
    icon_path: str | None = None


@dataclass
class AppSettings:
    """Application-wide settings.

    Attributes:
        action_delay_ms: Delay in milliseconds before executing an action
        overlay_size: Size of the overlay window in pixels
        show_animations: Whether to show animations
        replay_unselected: Whether to replay the original key if no item is selected
        long_press_delay_ms: Delay in milliseconds before showing the menu
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        language: UI language ('auto', 'en', 'ja')
        icon_size: Icon size in pixels
        text_size: Font size for menu item labels in points
        auto_scale_with_menu: Whether icon/text sizes scale automatically with menu size
        first_run: Whether this is the first run (shows welcome dialog)
    """

    action_delay_ms: int = 0
    overlay_size: int = 400
    show_animations: bool = False
    replay_unselected: bool = False
    long_press_delay_ms: int = 0
    log_level: str = "INFO"
    language: str = "auto"
    icon_size: int = 48
    text_size: int = 10
    auto_scale_with_menu: bool = True
    menu_opacity: int = 80
    key_sequence_delay_ms: int = 0
    first_run: bool = True


@dataclass
class MenuProfile:
    """A collection of items triggered by a specific hotkey"""

    name: str
    trigger_key: str
    items: list[PieSlice]
    target_apps: list[str] = field(default_factory=list)  # List of exe names or window titles. Empty = Global

    def __post_init__(self):
        if self.target_apps is None:
            self.target_apps = []


# Default configuration
DEFAULT_ITEMS = [
    PieSlice(label="取り消し", key="ctrl+z", color="#FF5252", icon_path="icons/undo.svg"),
    PieSlice(label="やり直し", key="ctrl+y", color="#448AFF", icon_path="icons/redo.svg"),
    PieSlice(label="ペン", key="p", color="#69F0AE", icon_path="icons/pencil.svg"),
    PieSlice(label="消しゴム", key="e", color="#FFD740", icon_path="icons/eraser.svg"),
    PieSlice(label="保存", key="ctrl+s", color="#40C4FF", icon_path="icons/save.svg"),
    PieSlice(label="選択解除", key="ctrl+d", color="#B0BEC5", icon_path="icons/lasso-select.svg"),
]

DEFAULT_TRIGGER = "ctrl+space"

DEFAULT_PROFILES = [MenuProfile(name="Default", trigger_key=DEFAULT_TRIGGER, items=DEFAULT_ITEMS)]


def load_config() -> tuple[list[MenuProfile], AppSettings]:
    """Load configuration from file.

    Handles migration from legacy formats and creates default config if needed.

    Returns:
        Tuple of (list of MenuProfile objects, AppSettings object)
    """
    logger.info("Loading configuration from file")

    _ensure_config_dir()

    if not os.path.exists(CONFIG_FILE):
        logger.info("Config file not found, creating default configuration")
        default_settings = AppSettings()
        save_config(DEFAULT_PROFILES, default_settings)
        return DEFAULT_PROFILES, default_settings

    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            # Very old format migration
            logger.info("Detected old list format, migrating")
            items = [PieSlice(**item) for item in data if isinstance(item, dict)]
            settings = AppSettings()
            profile = MenuProfile(name="Default", trigger_key=DEFAULT_TRIGGER, items=items)
            return [profile], settings

        elif isinstance(data, dict):
            schema_version = data.get("schema_version", 1)

            # Load app settings first
            settings_data = data.get("settings", {})
            # Only keep valid fields
            valid_fields = {
                k: v for k, v in settings_data.items() if k in AppSettings.__dataclass_fields__
            }
            settings = AppSettings(**valid_fields)
            logger.info(f"Loaded settings: {settings}")

            profiles = []
            if schema_version < 3:
                # Migrate version 2 (single trigger) to version 3 (multi profile)
                logger.info(f"Migrating schema version {schema_version} to 3")
                trigger_key = data.get("trigger_key", DEFAULT_TRIGGER)
                items_data = data.get("items", [])
                items = [PieSlice(**i) for i in items_data if isinstance(i, dict)]
                profiles.append(MenuProfile(name="Default", trigger_key=trigger_key, items=items))
            else:
                # Load existing profiles
                for p_data in data.get("profiles", []):
                    items = [PieSlice(**i) for i in p_data.get("items", [])]
                    profiles.append(
                        MenuProfile(
                            name=p_data.get("name", "Unnamed Profile"),
                            trigger_key=p_data.get("trigger_key", DEFAULT_TRIGGER),
                            items=items,
                            target_apps=p_data.get("target_apps", []),
                        )
                    )

            if not profiles:
                profiles = DEFAULT_PROFILES

            return profiles, settings
        else:
            logger.warning(f"Unexpected config format: {type(data)}")
            return DEFAULT_PROFILES, AppSettings()

    except json.JSONDecodeError as e:
        logger.error(f"Config file is corrupted (invalid JSON): {e}")
        # Backup corrupted file
        try:
            backup_file = CONFIG_FILE + ".backup"
            if os.path.exists(CONFIG_FILE):
                import shutil

                shutil.copy(CONFIG_FILE, backup_file)
                logger.info(f"Corrupted config backed up to: {backup_file}")
        except Exception as backup_error:
            logger.error(f"Failed to backup corrupted config: {backup_error}")
        return DEFAULT_PROFILES, AppSettings()
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return DEFAULT_PROFILES, AppSettings()


def save_config(profiles: list[MenuProfile], settings: AppSettings | None = None) -> bool:
    """Save configuration to file.

    Args:
        profiles: List of menu profiles to save
        settings: Application settings (uses defaults if None)

    Returns:
        True if save was successful, False otherwise
    """
    logger.info(f"Saving configuration: {len(profiles)} profiles")
    try:
        if settings is None:
            settings = AppSettings()

        data = {
            "schema_version": 4,  # Upgrade to version 4
            "profiles": [
                {
                    "name": p.name,
                    "trigger_key": p.trigger_key,
                    "target_apps": p.target_apps,
                    "items": [asdict(item) for item in p.items],
                }
                for p in profiles
            ],
            "settings": asdict(settings),
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Configuration saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False


# Load on module import
PROFILES, APP_SETTINGS = load_config()
