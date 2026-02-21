import sys
from unittest.mock import patch

import pytest
from pynput import keyboard as pynput_keyboard

from src.core.win32_input import MAGIC_EXTRA_INFO, send_pynput_key_safely


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_send_standard_key_win32():
    """Verify standard key (e.g. space) passes correct structure to SendInput."""
    with (
        patch("src.core.win32_input.user32.SendInput") as mock_send_input,
        patch("src.core.win32_input.ctypes.byref", side_effect=lambda x: x),
    ):
        mock_send_input.return_value = 1

        # Space key
        key = pynput_keyboard.Key.space
        send_pynput_key_safely(key, True)

        assert mock_send_input.called
        # Check first argument (nInputs)
        assert mock_send_input.call_args[0][0] == 1

        # Check the INPUT structure (now directly passed due to byref mock)
        inp = mock_send_input.call_args[0][1]
        assert inp.type == 1  # INPUT_KEYBOARD
        assert inp.ii.ki.wVk == 0x20  # VK_SPACE
        assert inp.ii.ki.dwExtraInfo == MAGIC_EXTRA_INFO
        assert inp.ii.ki.dwFlags == 0  # Press


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_send_char_key_win32():
    """Verify character key (e.g. 'a') passes correct structure to SendInput."""
    with (
        patch("src.core.win32_input.user32.SendInput") as mock_send_input,
        patch("src.core.win32_input.ctypes.byref", side_effect=lambda x: x),
    ):
        mock_send_input.return_value = 1

        key = pynput_keyboard.KeyCode.from_char("a")
        send_pynput_key_safely(key, False)  # Release

        assert mock_send_input.called
        inp = mock_send_input.call_args[0][1]
        # pynput character keys usually map VK 0x41 for 'a'
        assert inp.ii.ki.wVk == 0x41
        assert inp.ii.ki.dwFlags & 0x0002  # KEYEVENTF_KEYUP
        assert inp.ii.ki.dwExtraInfo == MAGIC_EXTRA_INFO


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_send_unicode_surrogate_win32():
    """Verify emoji/surrogate pair character uses KEYEVENTF_UNICODE path."""
    with patch("src.core.win32_input.user32.SendInput") as mock_send_input:
        # Note: surrogates path DOES NOT use byref on the individual inputs,
        # it passes the pointer directly to the array.
        mock_send_input.return_value = 1

        emoji = "😀"
        key = pynput_keyboard.KeyCode.from_char(emoji)

        send_pynput_key_safely(key, True)

        assert mock_send_input.called
        n_inputs = mock_send_input.call_args[0][0]
        assert n_inputs >= 1

        p_inputs = mock_send_input.call_args[0][1]
        # p_inputs is the (INPUT * N) instance.
        inp = p_inputs[0]
        assert inp.type == 1
        assert inp.ii.ki.wVk == 0
        assert inp.ii.ki.dwFlags & 0x0004  # KEYEVENTF_UNICODE
        assert inp.ii.ki.dwExtraInfo == MAGIC_EXTRA_INFO
