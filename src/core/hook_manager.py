"""Keyboard hook management for PieMenu.

Manages keyboard hooks for trigger keys using pynput, handles key press/release
events with proper modifier key state tracking, and coordinates with the
application to show/hide the pie menu.

Uses pynput's win32_event_filter for selective suppression on Windows.
Key insight: suppressed events do NOT reach on_press/on_release callbacks,
so all trigger logic must live inside win32_event_filter itself.
"""

import sys as _sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, ClassVar

from pynput import keyboard as pynput_keyboard

from src.core.keys import VK_TO_NAME, normalize_key_name, split_key_combo
from src.core.logger import get_logger
from src.core.win32_input import MAGIC_EXTRA_INFO, send_pynput_key_safely

logger = get_logger(__name__)

# Map from string modifier name (from trigger config) to Windows VK codes
_MOD_VK: dict[str, set[int]] = {
    "ctrl": {0xA2, 0xA3},  # VK_LCONTROL, VK_RCONTROL
    "alt": {0xA4, 0xA5},  # VK_LMENU, VK_RMENU
    "shift": {0xA0, 0xA1},  # VK_LSHIFT, VK_RSHIFT
    "windows": {0x5B, 0x5C},  # VK_LWIN, VK_RWIN
    "win": {0x5B, 0x5C},
}

# Windows Message Constants
WM_KEYDOWN = 0x100
WM_KEYUP = 0x101
WM_SYSKEYDOWN = 0x104
WM_SYSKEYUP = 0x105

# All modifier VKs (to track held state)
_ALL_MOD_VKS: dict[int, str] = {
    0xA2: "ctrl",
    0xA3: "ctrl",
    0xA4: "alt",
    0xA5: "alt",
    0xA0: "shift",
    0xA1: "shift",
    0x5B: "windows",
    0x5C: "windows",
}

# pynput Key → modifier name (for release_all_modifiers)
_PYNPUT_MOD_MAP: dict[Any, str] = {
    pynput_keyboard.Key.ctrl: "ctrl",
    pynput_keyboard.Key.ctrl_l: "ctrl",
    pynput_keyboard.Key.ctrl_r: "ctrl",
    pynput_keyboard.Key.alt: "alt",
    pynput_keyboard.Key.alt_l: "alt",
    pynput_keyboard.Key.alt_r: "alt",
    pynput_keyboard.Key.shift: "shift",
    pynput_keyboard.Key.shift_l: "shift",
    pynput_keyboard.Key.shift_r: "shift",
    pynput_keyboard.Key.cmd: "windows",
    pynput_keyboard.Key.cmd_l: "windows",
    pynput_keyboard.Key.cmd_r: "windows",
}


def _parse_key(name: str) -> pynput_keyboard.Key | pynput_keyboard.KeyCode:
    """Parse a key name string into a pynput key object.

    Raises:
        ValueError: If the name is not a known key. Unknown names used to fall
            back to their first character (e.g. ``pgup`` sent ``p``).
    """
    name = normalize_key_name(name)
    aliases: dict[str, pynput_keyboard.Key | pynput_keyboard.KeyCode] = {
        "escape": pynput_keyboard.Key.esc,
        "windows": pynput_keyboard.Key.cmd,
        "plus": pynput_keyboard.KeyCode.from_char("+"),
    }
    if name in aliases:
        return aliases[name]
    try:
        return pynput_keyboard.Key[name]
    except KeyError:
        pass
    if len(name) == 1:
        return pynput_keyboard.KeyCode.from_char(name)
    raise ValueError(f"Unknown key name: {name!r}")


# ──────────────────────────────────────────────────────────────────────────
# Windows Native Hook Implementation
# ──────────────────────────────────────────────────────────────────────────

if _sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    WH_KEYBOARD_LL = 13
    HC_ACTION = 0

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_: ClassVar[list[tuple[str, Any]]] = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
        ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
    )

    user32.SetWindowsHookExW.argtypes = (
        ctypes.c_int,
        LowLevelKeyboardProc,
        wintypes.HINSTANCE,
        wintypes.DWORD,
    )
    user32.SetWindowsHookExW.restype = wintypes.HHOOK

    user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL

    user32.CallNextHookEx.argtypes = (
        wintypes.HHOOK,
        ctypes.c_int,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
    user32.CallNextHookEx.restype = wintypes.LPARAM

    kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
    kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

    class _NativeWin32Hook:
        """A native WH_KEYBOARD_LL hook for Windows.

        This is needed because pynput's listener does not allow for safe,
        synchronous event suppression without causing threading deadlocks or
        ignoring the underlying OS message queue.
        """

        def __init__(self, filter_func: Callable[[int, Any], bool | None]):
            self.filter_func = filter_func
            self.hook_id: Any = None
            self.thread_id: Any = None
            self._thread: threading.Thread | None = None
            self._running = False
            self._hook_proc = LowLevelKeyboardProc(self._hook_callback)

        def _hook_callback(self, n_code: int, w_param: Any, l_param: Any) -> int:
            if n_code == HC_ACTION:
                kb_struct = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents

                # Extract the dwExtraInfo value safely
                extra_info = kb_struct.dwExtraInfo
                is_our_event = False
                if extra_info is not None:
                    # Depending on python/ctypes version, extra_info might be int or void_p object
                    val = (
                        extra_info
                        if isinstance(extra_info, int)
                        else getattr(extra_info, "value", 0)
                    )
                    if val == MAGIC_EXTRA_INFO:
                        is_our_event = True

                # Ignore events injected by our own application so we don't trap our own simulated keypresses
                # We NO LONGER check (kb_struct.flags & 0x10) because left-hand devices use it too!
                if not is_our_event and self.filter_func(w_param, kb_struct) is False:
                    # filter_func returns False to suppress the event
                    # Return non-zero to prevent the system from passing the
                    # message to the rest of the hook chain or to the target window.
                    return 1

            return int(user32.CallNextHookEx(self.hook_id, n_code, w_param, l_param))

        def start(self) -> None:
            self._running = True
            self._thread = threading.Thread(target=self._run_message_loop, daemon=True)
            self._thread.start()

        def _run_message_loop(self) -> None:
            self.thread_id = kernel32.GetCurrentThreadId()

            # Install the hook
            self.hook_id = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, self._hook_proc, kernel32.GetModuleHandleW(None), 0
            )

            if not self.hook_id:
                logger.error("Failed to install native keyboard hook!")
                return

            logger.info("Native Windows keyboard hook installed.")

            # Pump messages so the hook stays alive and responsive
            msg = wintypes.MSG()
            while self._running:
                # Use PeekMessage to not block indefinitely, allowing clean shutdown
                # PM_REMOVE = 0x0001
                if user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    time.sleep(0.01)

            # Cleanup
            user32.UnhookWindowsHookEx(self.hook_id)
            self.hook_id = None
            logger.info("Native Windows keyboard hook removed.")

        def stop(self) -> None:
            self._running = False
            if self._thread and self._thread.is_alive():
                # On Windows, threads pumping messages might need a nudge to wake up
                if self.thread_id:
                    # WM_QUIT = 0x0012
                    user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
                self._thread.join(timeout=1.0)

        def is_alive(self) -> bool:
            return self._thread is not None and self._thread.is_alive()


class HookManager:
    """Manages keyboard hooks for pie menu trigger keys using pynput.

    On Windows, uses win32_event_filter for selective key suppression.
    All trigger logic runs inside the filter because suppressed events
    do NOT reach on_press/on_release callbacks.

    Modifier key state is tracked via VK codes in the filter for accuracy.
    """

    def __init__(
        self,
        on_trigger_press: Callable[[str], None],
        on_trigger_release: Callable[[str], bool],
    ) -> None:
        self.on_trigger_press_callback = on_trigger_press
        self.on_trigger_release_callback = on_trigger_release

        self._listener: Any = None
        self._state_lock = threading.Lock()

        # {primary_key_name: [(sorted_modifier_tuple, full_trigger_str), ...]}
        self._trigger_configs: dict[str, list[tuple[tuple[str, ...], str]]] = {}

        # Currently suppressed primary keys: {key_name: full_trigger_str}
        self._active_suppressions: dict[str, str] = {}

        # Currently held modifier names (tracked via VK in win32_event_filter)
        self._held_modifiers: set[str] = set()

        # Press/release callbacks run off the hook thread (the hook must return
        # quickly) but on a single worker, so a release is never handled before
        # the press that preceded it.
        self._callback_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="hook-callback"
        )

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def start_hook(self, trigger_keys: list[str]) -> None:
        """Start hooking the given trigger key combinations."""
        logger.info(f"HookManager: Starting hook with triggers: {trigger_keys}")
        with self._state_lock:
            self._stop_listener_unsafe()
            self._trigger_configs = {}
            self._active_suppressions = {}
            self._held_modifiers = set()

            for full_key in trigger_keys:
                parts = split_key_combo(full_key)
                if not parts:
                    continue
                primary = parts[-1]
                modifiers = tuple(sorted(parts[:-1]))
                self._trigger_configs.setdefault(primary, []).append((modifiers, full_key))
                logger.debug(
                    f"Registered trigger: {primary} with modifiers {modifiers} (full: {full_key})"
                )

        try:
            logger.info("HookManager: Calling _start_listener...")
            self._start_listener()
            logger.info(
                f"HookManager: _start_listener() returned. Listener alive: {self._listener.is_alive() if self._listener else 'No'}"
            )
        except Exception as e:
            logger.error(f"HookManager: Failed to start listener: {e}", exc_info=True)

        logger.info(
            f"HookManager: Hooked {len(self._trigger_configs)} primary keys "
            f"for {len(trigger_keys)} menus. Listener: {self._listener}"
        )

    def stop_hook(self) -> None:
        """Stop all hooks."""
        with self._state_lock:
            self._stop_listener_unsafe()
            self._active_suppressions.clear()
            self._held_modifiers.clear()

    def unhook_all(self) -> None:
        """Unhook everything (alias for stop_hook)."""
        self.stop_hook()

    def release_all_modifiers(self) -> None:
        """Release any modifier keys currently tracked as held.

        Call this before executing an action to prevent modifier leakage.
        """
        with self._state_lock:
            held = set(self._held_modifiers)

        mod_to_pynput = {
            "ctrl": pynput_keyboard.Key.ctrl,
            "alt": pynput_keyboard.Key.alt,
            "shift": pynput_keyboard.Key.shift,
            "windows": pynput_keyboard.Key.cmd,
        }

        for mod_name in held:
            key = mod_to_pynput.get(mod_name)
            if key:
                try:
                    send_pynput_key_safely(key, False)
                    logger.debug(f"Released held modifier: {mod_name}")
                except Exception as exc:
                    logger.debug(f"Could not release {mod_name}: {exc}")

    # ──────────────────────────────────────────────────────────────────────
    # Listener lifecycle
    # ──────────────────────────────────────────────────────────────────────

    def _start_listener(self) -> None:
        """Start the pynput listener (or native hook on Windows)."""
        import sys as _sys

        try:
            if _sys.platform == "win32":
                logger.info("HookManager: Creating Windows native listener...")
                self._listener = _NativeWin32Hook(
                    filter_func=self._win32_event_filter,
                )
            else:
                logger.info(f"HookManager: Creating {_sys.platform} pynput listener...")
                self._listener = pynput_keyboard.Listener(
                    on_press=self._on_press_passthrough,
                    on_release=self._on_release_passthrough,
                )

            logger.info("HookManager: Starting listener thread...")
            self._listener.start()
        except Exception as e:
            logger.error(f"HookManager: Error in _start_listener: {e}", exc_info=True)
            raise

    def _stop_listener_unsafe(self) -> None:
        """Stop listener without acquiring lock (caller must hold lock)."""
        if self._listener is not None:
            import contextlib

            with contextlib.suppress(Exception):
                self._listener.stop()
            self._listener = None

    # ──────────────────────────────────────────────────────────────────────
    # Windows event filter — all trigger logic lives here
    # ──────────────────────────────────────────────────────────────────────

    def _win32_event_filter(self, msg: int, data: Any) -> bool | None:
        """Win32 low-level keyboard hook filter.

        IMPORTANT: Suppressed events do NOT reach on_press/on_release.
        Therefore all trigger detection and callback invocation happens here.

        msg values:
            WM_KEYDOWN    = 0x100
            WM_KEYUP      = 0x101
            WM_SYSKEYDOWN = 0x104
            WM_SYSKEYUP   = 0x105
        """
        vk = data.vkCode
        is_press = msg in (WM_KEYDOWN, WM_SYSKEYDOWN)
        is_release = msg in (WM_KEYUP, WM_SYSKEYUP)

        # ── Track modifier state ──────────────────────────────────────────
        mod_name = _ALL_MOD_VKS.get(vk)
        if mod_name:
            with self._state_lock:
                if is_press and mod_name not in self._held_modifiers:
                    self._held_modifiers.add(mod_name)
                    logger.debug(f"MODIFIER ADDED: {mod_name} (Current: {self._held_modifiers})")
                elif is_release and mod_name in self._held_modifiers:
                    self._held_modifiers.discard(mod_name)
                    logger.debug(f"MODIFIER REMOVED: {mod_name} (Current: {self._held_modifiers})")
                # Modifier keys ALSO need to be checked as primary trigger keys
                # (e.g. if trigger is 'ctrl' alone) — check inside the same lock!
                is_also_trigger = mod_name in self._trigger_configs
            if not is_also_trigger:
                return True  # Just a modifier, pass through
            # else: fall through to primary key logic below

        # ── Resolve primary key name ──────────────────────────────────────
        key_name = VK_TO_NAME.get(vk) or _ALL_MOD_VKS.get(vk)
        if key_name is None:
            return True  # Unknown key — pass through

        # ── Check if this key is currently suppressed (release phase) ─────
        with self._state_lock:
            suppressed_trigger = self._active_suppressions.get(key_name)

        if is_release and suppressed_trigger is not None:
            # Suppress the release and fire the release callback
            with self._state_lock:
                self._active_suppressions.pop(key_name, None)

            self._dispatch(self._handle_release, suppressed_trigger, key_name)
            return False

        if is_press:
            with self._state_lock:
                if key_name in self._active_suppressions:
                    return False

                configs = self._trigger_configs.get(key_name, [])
                # A modifier used as the primary key (e.g. trigger "ctrl") is
                # itself in _held_modifiers by now; don't count it twice.
                held_tuple = tuple(sorted(self._held_modifiers - {key_name}))

                # Check for matches immediately while we hold the lock to avoid
                # having to resolve race conditions later
                matched_trigger = None
                if configs:
                    for mod_tuple, full_key in configs:
                        if mod_tuple == held_tuple:
                            matched_trigger = full_key
                            break

                if matched_trigger:
                    logger.info(f"Trigger MATCH: {matched_trigger}. Suppressing {key_name}.")
                    self._active_suppressions[key_name] = matched_trigger

                    self._dispatch(self.on_trigger_press_callback, matched_trigger)
                    return False

        return True  # Pass through

    def _dispatch(self, func: Callable[..., Any], *args: Any) -> None:
        """Run a callback on the ordered callback worker."""

        def run() -> None:
            try:
                func(*args)
            except Exception as e:
                logger.error(f"HookManager: callback {func} failed: {e}", exc_info=True)

        try:
            self._callback_executor.submit(run)
        except RuntimeError as e:  # executor shut down during exit
            logger.debug(f"HookManager: dropping callback during shutdown: {e}")

    def _handle_release(self, trigger: str, key_name: str) -> None:
        """Handle trigger release: call callback and replay if not consumed."""
        consumed = self.on_trigger_release_callback(trigger)
        if not consumed:
            self._replay_key(key_name)

    # ──────────────────────────────────────────────────────────────────────
    # Passthrough callbacks (for non-Windows or non-suppressed events)
    # ──────────────────────────────────────────────────────────────────────

    def _on_press_passthrough(
        self, key: pynput_keyboard.Key | pynput_keyboard.KeyCode | None
    ) -> None:
        """Track modifier state for non-Windows platforms."""
        if key is None:
            return
        mod = _PYNPUT_MOD_MAP.get(key)
        if mod:
            with self._state_lock:
                self._held_modifiers.add(mod)

    def _on_release_passthrough(
        self, key: pynput_keyboard.Key | pynput_keyboard.KeyCode | None
    ) -> None:
        """Track modifier state for non-Windows platforms."""
        if key is None:
            return
        mod = _PYNPUT_MOD_MAP.get(key)
        if mod:
            with self._state_lock:
                self._held_modifiers.discard(mod)

    # ──────────────────────────────────────────────────────────────────────
    # Key replay
    # ──────────────────────────────────────────────────────────────────────

    def _replay_key(self, key_name: str) -> None:
        """Replay a key press+release using the custom injector."""
        try:
            key = _parse_key(key_name)
            send_pynput_key_safely(key, True)  # Press
            send_pynput_key_safely(key, False)  # Release
            logger.debug(f"Replayed key: {key_name}")
        except Exception as exc:
            logger.warning(f"Failed to replay key '{key_name}': {exc}")
