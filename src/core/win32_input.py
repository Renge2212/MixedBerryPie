import ctypes
import sys
from ctypes import wintypes
from typing import ClassVar

from pynput import keyboard as pynput_keyboard

from src.core.logger import get_logger

# Magic extra info to identify our own injected events
MAGIC_EXTRA_INFO = 0x31415926

if sys.platform == "win32":
    # Use WinDLL with use_last_error=True to correctly capture GetLastError
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    INPUT_KEYBOARD = 1
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    KEYEVENTF_UNICODE = 0x0004

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class InputUnion(ctypes.Union):
        _fields_: ClassVar = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_: ClassVar = [("type", wintypes.DWORD), ("ii", InputUnion)]

    def _send_key_win32(vk: int, is_press: bool) -> None:
        """Send a keyboard event with our magic dwExtraInfo so HookManager can ignore it."""
        try:
            extra = ctypes.c_void_p(MAGIC_EXTRA_INFO)
            flags = 0

            # Simple extended key detection for modifiers and arrows
            if vk in (0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B, 0x5C):
                flags |= KEYEVENTF_EXTENDEDKEY

            # Map virtual key to scan code (MAPVK_VK_TO_VSC = 0)
            scan = user32.MapVirtualKeyW(vk, 0)

            if not is_press:
                flags |= KEYEVENTF_KEYUP

            ki = KEYBDINPUT(vk, scan, flags, 0, extra)
            ii = InputUnion(ki=ki)
            inp = INPUT(type=INPUT_KEYBOARD, ii=ii)

            res = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            if res == 0:
                err = ctypes.get_last_error()
                logger.error(f"Failed to send key win32 (VK={vk}, Error={err})")
        except Exception as e:
            logger.error(f"Failed to send key win32 (VK={vk}): {e}")


# Global controller for fallback
_fallback_controller = pynput_keyboard.Controller()

# Set up module-level logger
logger = get_logger("win32_input")

if sys.platform == "win32":
    logger.debug(f"INPUT structure size: {ctypes.sizeof(INPUT)} bytes")


def send_pynput_key_safely(key, is_press: bool):
    """
    Send a pynput key using our custom injector with extra info.

    Args:
        key: The Key or KeyCode object to send.
        is_press: True for press, False for release.
    """
    if sys.platform == "win32":
        try:
            # We want to do exactly what pynput does, but add our dwExtraInfo
            target_key = (
                key.value if hasattr(key, "value") and hasattr(key.value, "_parameters") else key
            )

            if hasattr(target_key, "_parameters"):
                params = target_key._parameters(is_press)
                extra = ctypes.c_void_p(MAGIC_EXTRA_INFO)

                # Check if params is a dict (standard key) or if we need to handle surrogate pairs
                # pynput raises ValueError in _parameters(is_press) if it's a surrogate pair
                ki = KEYBDINPUT(
                    wVk=params.get("wVk", 0),
                    wScan=params.get("wScan", 0),
                    dwFlags=params.get("dwFlags", 0),
                    time=0,
                    dwExtraInfo=extra,
                )
                ii = InputUnion(ki=ki)
                inp = INPUT(type=INPUT_KEYBOARD, ii=ii)

                res = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
                if res == 0:
                    err = ctypes.get_last_error()
                    logger.error(
                        f"SendInput FAILED (Error={err}): VK={ki.wVk:02X}, Scan={ki.wScan:02X}, Flags={ki.dwFlags:04X}"
                    )
                else:
                    logger.debug(f"SendInput SUCCESS: VK={ki.wVk:02X}, Flags={ki.dwFlags:04X}")
                return
        except ValueError:
            # Handle unicode surrogates exactly like pynput does, but with our extra_info
            try:
                byte_data = bytearray(key.char.encode("utf-16le"))
                surrogates = [
                    byte_data[i] | (byte_data[i + 1] << 8) for i in range(0, len(byte_data), 2)
                ]

                state_flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if not is_press else 0)
                extra = ctypes.c_void_p(MAGIC_EXTRA_INFO)

                inputs = (INPUT * len(surrogates))(
                    *(
                        INPUT(
                            INPUT_KEYBOARD,
                            InputUnion(
                                ki=KEYBDINPUT(
                                    wVk=0,
                                    wScan=scan,
                                    dwFlags=state_flags,
                                    time=0,
                                    dwExtraInfo=extra,
                                )
                            ),
                        )
                        for scan in surrogates
                    )
                )

                res = user32.SendInput(len(surrogates), inputs, ctypes.sizeof(INPUT))
                if res == 0:
                    err = ctypes.get_last_error()
                    logger.error(f"SendInput Unicode FAILED (Error={err}): {surrogates}")
                else:
                    logger.debug(f"SendInput Unicode SUCCESS: {surrogates}")
                return
            except Exception as e:
                logger.error(f"Failed surrogate injection for {key}: {e}")
        except Exception as e:
            logger.error(f"Failed to use pynput _parameters for {key}: {e}")
            # Fall through to raw vk

        # Fallback to pure VK injection if key lacks _parameters
        vk = None
        if hasattr(key, "value") and hasattr(key.value, "vk"):
            vk = key.value.vk
        elif hasattr(key, "vk"):
            vk = key.vk

        if vk is not None:
            _send_key_win32(vk, is_press)
            return

    # Fallback (non-win32 Linux/Mac)
    try:
        if is_press:
            _fallback_controller.press(key)
        else:
            _fallback_controller.release(key)
    except Exception as e:
        logger.error(f"Failed to send pynput key {key}: {e}")


def get_active_window_info() -> tuple[str | None, str | None]:
    """Get the executable name and title of the foreground window on Windows."""
    if sys.platform != "win32":
        return None, None

    try:
        import os

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None, None

        # Window Title
        length = user32.GetWindowTextLengthW(hwnd)
        title_buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buf, length + 1)
        title = title_buf.value

        # Process Name
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        # 0x0400: PROCESS_QUERY_INFORMATION, 0x0010: PROCESS_VM_READ
        h_process = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)

        if h_process:
            try:
                exe_buf = ctypes.create_unicode_buffer(1024)
                kernel32.K32GetModuleFileNameExW(h_process, None, exe_buf, 1024)
                full_path = exe_buf.value
                exe_name = os.path.basename(full_path).lower() if full_path else ""
            finally:
                kernel32.CloseHandle(h_process)
            return exe_name, title
        else:
            return None, title
    except Exception as e:
        logger.error(f"Error getting active window info: {e}")
        return None, None
