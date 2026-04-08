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
_HASH_CHUNK_SIZE = 65536  # Chunk size for SHA-256 file hashing (bytes)


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


def _hash_file(path: str) -> str:
    """Compute SHA-256 hash of a file using chunked reads."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_HASH_CHUNK_SIZE), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _find_duplicate_in_dir(directory: str, src_hash: str) -> str | None:
    """Find an existing file in directory with the same content hash."""
    for name in os.listdir(directory):
        file_path = os.path.join(directory, name)
        if os.path.isfile(file_path):
            with open(file_path, "rb") as f:
                if hashlib.sha256(f.read()).hexdigest() == src_hash:
                    return file_path
    return None


def _copy_with_collision_handling(src: str, dest_dir: str) -> str:
    """Copy a file to dest_dir, renaming on name collision."""
    base_name = os.path.basename(src)
    dest_path = os.path.join(dest_dir, base_name)

    if os.path.exists(dest_path):
        name, ext = os.path.splitext(base_name)
        counter = 1
        while os.path.exists(os.path.join(dest_dir, f"{name}_{counter}{ext}")):
            counter += 1
        dest_path = os.path.join(dest_dir, f"{name}_{counter}{ext}")

    if os.path.abspath(src) != os.path.abspath(dest_path):
        shutil.copy2(src, dest_path)
        logger.info(f"Assetized icon: {src} -> {dest_path}")
    return dest_path


def _normalize_icon_path(path: str) -> str:
    """Convert an absolute path inside USER_ICONS_DIR to a relative path."""
    abs_prefix = os.path.abspath(USER_ICONS_DIR) + os.sep
    if os.path.abspath(path).startswith(abs_prefix):
        return os.path.relpath(path, CONFIG_DIR).replace("\\", "/")
    return path


def _icon_path_to_abs(path: str) -> str:
    """Resolve an icon history entry to an absolute path for comparison."""
    if not os.path.isabs(path) and path.startswith("user_icons"):
        return os.path.abspath(os.path.join(CONFIG_DIR, path))
    return os.path.abspath(path)


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
    os.makedirs(USER_ICONS_DIR, exist_ok=True)

    final_path = path

    # If already in USER_ICONS_DIR, no need to copy
    abs_prefix = os.path.abspath(USER_ICONS_DIR) + os.sep
    if not os.path.abspath(path).startswith(abs_prefix):
        try:
            src_hash = _hash_file(path)
            duplicate = _find_duplicate_in_dir(USER_ICONS_DIR, src_hash)
            if duplicate:
                logger.info(f"Duplicate content found, reusing: {duplicate}")
                final_path = duplicate
            else:
                final_path = _copy_with_collision_handling(path, USER_ICONS_DIR)
        except Exception as e:
            logger.error(f"Failed to assetize icon: {e}")

    final_path = _normalize_icon_path(final_path)

    # Deduplicate history entries
    target_abs = _icon_path_to_abs(final_path)
    history = [p for p in load_icon_history() if _icon_path_to_abs(p) != target_abs]
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


def _validate_setting_type(value: object, default: object) -> bool:
    """Validate that a config value matches the expected type of its default.

    Handles the bool/int subclass issue (JSON has no bool distinction from int
    in Python's isinstance) and validates nested dict/list structures for known
    complex settings.
    """
    # bool must be checked first because bool is a subclass of int
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, type(default))


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
                    default_v = getattr(default_settings, k)
                    if _validate_setting_type(v, default_v):
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
