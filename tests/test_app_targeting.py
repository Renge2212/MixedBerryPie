from unittest.mock import patch

from src.core.win32_input import get_open_windows


def test_get_open_windows_platform_guard():
    """Verify get_open_windows returns empty list on non-Windows."""
    with patch("sys.platform", "linux"):
        assert get_open_windows() == []
