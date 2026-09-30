"""Canonical key names shared by the key recorder, the hook and the key sender.

The recorder (Qt), the low-level hook (Windows VK codes) and the sender (pynput)
each have their own naming for keys. Everything is normalized to the names used
here so that a recorded combo matches the hook and is sent as the intended key.
"""

# Windows VK code → canonical key name
VK_TO_NAME: dict[int, str] = {
    0x20: "space",
    0x0D: "enter",
    0x09: "tab",
    0x1B: "escape",
    0x08: "backspace",
    0x2E: "delete",
    0x2D: "insert",
    0x24: "home",
    0x23: "end",
    0x21: "page_up",
    0x22: "page_down",
    0x26: "up",
    0x28: "down",
    0x25: "left",
    0x27: "right",
    **{0x70 + i: f"f{i + 1}" for i in range(24)},  # F1-F24
    **{0x41 + i: chr(ord("a") + i) for i in range(26)},  # A-Z → a-z
    **{0x30 + i: str(i) for i in range(10)},  # 0-9
}

# Alternative spellings (Qt's QKeySequence names, pynput names, common short forms)
KEY_ALIASES: dict[str, str] = {
    "esc": "escape",
    "return": "enter",
    "pgup": "page_up",
    "pageup": "page_up",
    "pgdown": "page_down",
    "pagedown": "page_down",
    "del": "delete",
    "ins": "insert",
    "control": "ctrl",
    "win": "windows",
    "meta": "windows",
    "cmd": "windows",
    "+": "plus",
}


def normalize_key_name(name: str) -> str:
    """Return the canonical name for a single key."""
    name = name.strip().lower()
    return KEY_ALIASES.get(name, name)


def split_key_combo(combo: str) -> list[str]:
    """Split a combo such as ``ctrl+shift+pgup`` into canonical key names.

    A literal plus key is supported both as ``plus`` and as a trailing ``+``
    (``ctrl++``).
    """
    combo = combo.strip().lower()
    if not combo:
        return []
    trailing_plus = combo.endswith("+")
    parts = [p for p in combo.split("+") if p.strip()]
    if trailing_plus:
        parts.append("+")
    return [normalize_key_name(p) for p in parts]


def normalize_key_combo(combo: str) -> str:
    """Return ``combo`` with every key name in canonical form."""
    return "+".join(split_key_combo(combo))
