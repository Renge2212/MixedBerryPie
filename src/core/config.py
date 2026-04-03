"""Configuration management for PieMenu application.

This module handles loading, saving, and migrating configuration files.
It defines the core data structures (PieSlice, AppSettings, MenuProfile)
and provides functions to persist them to disk.
"""

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field

from src.core.logger import get_logger

logger = get_logger(__name__)

# Config Path Resolution (AppData)
APP_NAME = "MixedBerryPie"
APPDATA = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
CONFIG_DIR = os.path.join(APPDATA, APP_NAME)
CONFIG_FILE = os.path.join(CONFIG_DIR, "menu_config.json")
ICON_HISTORY_FILE = os.path.join(CONFIG_DIR, "icon_history.json")
USER_ICONS_DIR = os.path.join(CONFIG_DIR, "user_icons")
ICON_HISTORY_MAX = 100


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


def load_icon_history() -> list[str]:
    """Load the icon usage history from disk.

    Returns:
        List of absolute icon paths, most recent first. Empty list on error.
    """
    _ensure_config_dir()
    if not os.path.exists(ICON_HISTORY_FILE):
        return []
    try:
        with open(ICON_HISTORY_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [p for p in data if isinstance(p, str)]
    except Exception as e:
        logger.warning(f"Could not load icon history: {e}")
    return []


def save_icon_history(paths: list[str]) -> None:
    """Persist the icon history list to disk (capped at ICON_HISTORY_MAX)."""
    _ensure_config_dir()
    try:
        with open(ICON_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(paths[:ICON_HISTORY_MAX], f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Could not save icon history: {e}")


def add_to_icon_history(path: str) -> list[str]:
    """Assetize icon and prepend to history.

    If the icon is external, it's copied to the user_icons directory.
    Deduplicates and persists to disk.

    Args:
        path: Absolute path to the icon file.

    Returns:
        Updated history list.
    """
    if not os.path.exists(path):
        return load_icon_history()

    _ensure_config_dir()
    if not os.path.exists(USER_ICONS_DIR):
        os.makedirs(USER_ICONS_DIR, exist_ok=True)

    final_path = path

    # If already in USER_ICONS_DIR, no need to copy
    # Use os.sep suffix to prevent path-traversal false positives (e.g. user_icons_evil/)
    _user_icons_abs = os.path.abspath(USER_ICONS_DIR) + os.sep
    if not os.path.abspath(path).startswith(_user_icons_abs):
        # Copy external icon to user_icons dir
        base_name = os.path.basename(path)
        dest_path = os.path.join(USER_ICONS_DIR, base_name)

        # Hashing-based duplicate check (SHA-256) — chunked to avoid OOM on large files
        try:
            sha = hashlib.sha256()
            with open(path, "rb") as bf:
                for chunk in iter(lambda: bf.read(65536), b""):
                    sha.update(chunk)
            src_hash = sha.hexdigest()

            # Check existing files in user_icons
            for f in os.listdir(USER_ICONS_DIR):
                f_path = os.path.join(USER_ICONS_DIR, f)
                if os.path.isfile(f_path):
                    with open(f_path, "rb") as obf:
                        if hashlib.sha256(obf.read()).hexdigest() == src_hash:
                            logger.info(f"Duplicate content found, reusing: {f_path}")
                            final_path = f_path
                            break

            if final_path == path:  # Not found in loop
                # Handle name collisions for different content
                if os.path.exists(dest_path):
                    name, ext = os.path.splitext(base_name)
                    counter = 1
                    while os.path.exists(os.path.join(USER_ICONS_DIR, f"{name}_{counter}{ext}")):
                        counter += 1
                    dest_path = os.path.join(USER_ICONS_DIR, f"{name}_{counter}{ext}")

                if os.path.abspath(path) != os.path.abspath(dest_path):
                    shutil.copy2(path, dest_path)
                    logger.info(f"Assetized icon: {path} -> {dest_path}")
                final_path = dest_path
        except Exception as e:
            logger.error(f"Failed to assetize icon: {e}")
            # Fallback to original path if copy fails

    history = load_icon_history()
    # Normalize final_path to relative if it's in USER_ICONS_DIR
    _user_icons_abs = os.path.abspath(USER_ICONS_DIR) + os.sep
    if os.path.abspath(final_path).startswith(_user_icons_abs):
        final_path = os.path.relpath(final_path, CONFIG_DIR).replace("\\", "/")

    # Remove duplicates (comparing absolute paths internally for reliability)
    def to_abs(p):
        if not os.path.isabs(p) and p.startswith("user_icons"):
            return os.path.abspath(os.path.join(CONFIG_DIR, p))
        return os.path.abspath(p)

    target_abs = to_abs(final_path)
    history = [p for p in history if to_abs(p) != target_abs]

    history.insert(0, final_path)
    history = history[:ICON_HISTORY_MAX]
    save_icon_history(history)
    return history


def remove_from_icon_history(path: str) -> list[str]:
    """Remove an icon from history and delete its file if it's in user_icons.

    Args:
        path: Absolute path to the icon to remove.

    Returns:
        Updated history list.
    """
    history = load_icon_history()
    new_history = [p for p in history if os.path.abspath(p) != os.path.abspath(path)]

    if len(new_history) != len(history):
        save_icon_history(new_history)
        # If the file is in our managed directory, delete it
        _user_icons_abs = os.path.abspath(USER_ICONS_DIR) + os.sep
        if os.path.abspath(path).startswith(_user_icons_abs):
            try:
                if os.path.exists(path):
                    os.remove(path)
                    logger.info(f"Deleted user icon asset: {path}")
            except Exception as e:
                logger.error(f"Failed to delete icon asset: {e}")

    return new_history


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
    action_type: str = "key"  # 'key', 'url', 'cmd', 'submenu', 'back'
    icon_path: str | None = None
    submenu_items: list["PieSlice"] = field(default_factory=list)


# Beautiful thematic color palettes for the "Preset" mode
COLOR_PRESETS = {
    "Mixed Berry": ["#FF1744", "#D500F9", "#2979FF", "#E91E63", "#673AB7", "#3F51B5"],
    "Vibrant": ["#E91E63", "#9C27B0", "#2196F3", "#00BCD4", "#4CAF50", "#FFC107"],
    "Pastel": ["#FFB7B2", "#FFDAC1", "#E2F0CB", "#B5EAD7", "#C7CEEA", "#6EB5FF"],
    "Ocean": ["#00B4D8", "#0077B6", "#023E8A", "#03045E", "#90E0EF", "#CAF0F8"],
    "Forest": ["#2D6A4F", "#40916C", "#52B788", "#74C69D", "#95D5B2", "#B7E4C7"],
    "Cyberpunk": ["#F0ED69", "#69F0ED", "#ED69F0", "#F06969", "#69EDF0", "#6972F0"],
    "Monochrome": ["#212121", "#424242", "#616161", "#757575", "#9E9E9E", "#BDBDBD"],
    "Fire": ["#D00000", "#FF0000", "#FF4800", "#FF7B00", "#FFB700", "#FFD000"],
}


@dataclass
class AppSettings:
    """Application-wide settings.

    Attributes:
        action_delay_ms: Delay in milliseconds before executing an action
        overlay_size: Size of the overlay window in pixels
        show_animations: Whether to show animations
        replay_unselected: Whether to replay the original key if no item is selected
        long_press_delay_ms: Time in ms to wait before showing menu overlay
        language: Language code (auto, en, ja)')
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
    language: str = "auto"
    icon_size: int = 64
    text_size: int = 9
    auto_scale_with_menu: bool = True
    menu_opacity: int = 60
    key_sequence_delay_ms: int = 0
    font_family: str = "Noto Sans JP"
    enable_text_outline: bool = True
    dim_background: bool = True
    dynamic_text_color: bool = False
    color_mode: str = "preset"  # 'individual', 'unified', 'preset'
    unified_color: str = "#448AFF"
    selected_preset: str = "Mixed Berry"
    custom_presets: dict[str, list[str]] = field(default_factory=dict)
    first_run: bool = True
    enable_file_logging: bool = False


@dataclass
class MenuProfile:
    """A collection of items triggered by a specific hotkey"""

    name: str
    trigger_key: str
    items: list[PieSlice]
    target_apps: list[str] = field(
        default_factory=list
    )  # List of exe names or window titles. Empty = Global

    def __post_init__(self):
        if self.target_apps is None:
            self.target_apps = []


def _parse_slice(data: dict) -> PieSlice:
    """Recursively parse a dictionary into a PieSlice object."""
    submenu_data = data.get("submenu_items", [])
    submenus = [_parse_slice(child) for child in submenu_data if isinstance(child, dict)]

    return PieSlice(
        label=data.get("label", ""),
        key=data.get("key", ""),
        color=data.get("color", "#CCCCCC"),
        action_type=data.get("action_type", "key"),
        icon_path=data.get("icon_path"),
        submenu_items=submenus,
    )


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
            # Only keep valid fields and validate types
            valid_fields = {}
            default_settings = AppSettings()
            for k, v in settings_data.items():
                if k in AppSettings.__dataclass_fields__:
                    # Simple type validation against default values
                    default_v = getattr(default_settings, k)
                    if isinstance(v, type(default_v)):
                        valid_fields[k] = v
                    else:
                        logger.warning(
                            f"Setting '{k}' has invalid type {type(v)}, using default {type(default_v)}"
                        )
            settings = AppSettings(**valid_fields)
            logger.info(f"Loaded validated settings: {settings}")

            profiles = []
            if schema_version < 3:
                # Migrate version 2 (single trigger) to version 3 (multi profile)
                logger.info(f"Migrating schema version {schema_version} to 3")
                trigger_key = data.get("trigger_key", DEFAULT_TRIGGER)
                items_data = data.get("items", [])
                items = [_parse_slice(i) for i in items_data if isinstance(i, dict)]
                profiles.append(MenuProfile(name="Default", trigger_key=trigger_key, items=items))
            else:
                # Load existing profiles
                for p_data in data.get("profiles", []):
                    items = [_parse_slice(i) for i in p_data.get("items", [])]
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
            "schema_version": 5,  # Upgrade to version 5 (Nested Slices)
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
        # Atomic write using a temporary file
        fd, temp_path = tempfile.mkstemp(dir=CONFIG_DIR, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Atomic replace
            os.replace(temp_path, CONFIG_FILE)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e

        logger.info("Configuration saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False
