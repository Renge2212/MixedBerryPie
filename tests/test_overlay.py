from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QPainterPath

from src.core.config import AppSettings, PieSlice
from src.ui.overlay import PieOverlay

# qapp fixture is provided by conftest.py


@pytest.fixture
def overlay_setup(qapp):
    """Fixture to provide a PieOverlay instance with sample items."""
    test_items = [
        PieSlice(label="North", key="n", color="#FF0000"),
        PieSlice(label="East", key="e", color="#00FF00"),
        PieSlice(label="South", key="s", color="#0000FF"),
        PieSlice(label="West", key="w", color="#FFFF00"),
    ]
    settings = AppSettings()
    # Disable animations for testing to ensure synchronous behavior
    settings.show_animations = False
    overlay = PieOverlay(test_items, settings)
    overlay.is_visible = True

    yield overlay, settings, test_items

    overlay.close()
    overlay.deleteLater()


def test_initialization(overlay_setup):
    overlay, _, _ = overlay_setup
    assert len(overlay.menu_items) == 4
    assert overlay.active_path == []
    assert overlay.radius_inner == 50
    # radius_outer is calculated: min(200, overlay_size // 2 - 50)
    # Default overlay_size is 400, so 400 // 2 = 200.
    assert overlay.radius_outer == 200


def test_empty_items_list(qapp):
    """Test overlay with empty items list"""
    settings = AppSettings()
    empty_overlay = PieOverlay([], settings)
    assert len(empty_overlay.menu_items) == 0

    # Should not crash when updating selection
    empty_overlay.update_selection(QPoint(100, 100))
    assert empty_overlay.active_path == []

    empty_overlay.close()


def test_single_item(qapp):
    """Test overlay with single item"""
    settings = AppSettings()
    single_overlay = PieOverlay([PieSlice(label="Only", key="o", color="#FF0000")], settings)
    single_overlay.is_visible = True

    # Any position outside inner radius should select item 0
    single_overlay.center_pos = QPoint(250, 250)
    single_overlay.update_selection(QPoint(350, 250))  # Right of center
    assert single_overlay.active_path == [0]

    single_overlay.close()


def test_selection_inside_inner_radius(overlay_setup):
    overlay, _, _ = overlay_setup
    overlay.center_pos = QPoint(250, 250)

    # Position very close to center (within inner radius of 20)
    # Inner radius is 62 actually per test_initialization
    overlay.update_selection(QPoint(255, 255))
    assert overlay.active_path == []


def test_selection_angle_calculation_north(overlay_setup):
    overlay, _, _ = overlay_setup
    overlay.center_pos = QPoint(250, 250)

    # Position directly above center (North)
    overlay.update_selection(QPoint(250, 150))  # 100 pixels up
    assert overlay.active_path == [0]


def test_selection_angle_calculation_east(overlay_setup):
    overlay, _, _ = overlay_setup
    overlay.center_pos = QPoint(250, 250)

    # Position directly right of center (East)
    overlay.update_selection(QPoint(350, 250))  # 100 pixels right
    assert overlay.active_path == [1]


def test_selection_angle_calculation_south(overlay_setup):
    overlay, _, _ = overlay_setup
    overlay.center_pos = QPoint(250, 250)

    # Position directly below center (South)
    overlay.update_selection(QPoint(250, 350))  # 100 pixels down
    assert overlay.active_path == [2]


def test_selection_angle_calculation_west(overlay_setup):
    overlay, _, _ = overlay_setup
    overlay.center_pos = QPoint(250, 250)

    # Position directly left of center (West)
    overlay.update_selection(QPoint(150, 250))  # 100 pixels left
    assert overlay.active_path == [3]


def test_selection_with_six_items(qapp):
    """Test selection with 6 items (60 degrees each)"""
    settings = AppSettings()
    six_items = [PieSlice(label=f"Item{i}", key=f"{i}", color="#FF0000") for i in range(6)]
    overlay = PieOverlay(six_items, settings)
    overlay.is_visible = True
    overlay.center_pos = QPoint(250, 250)

    # Test each item
    test_positions = [
        (250, 150, 0),  # North
        (350, 200, 1),  # NE
        (350, 300, 2),  # SE
        (250, 350, 3),  # South
        (150, 300, 4),  # SW
        (150, 200, 5),  # NW
    ]

    for x, y, expected_index in test_positions:
        overlay.update_selection(QPoint(x, y))
        assert overlay.active_path == [expected_index], (
            f"Position ({x}, {y}) should select item {expected_index}"
        )

    overlay.close()


def test_hide_menu_without_selection(overlay_setup):
    """Test hiding menu without selection doesn't emit signal"""
    overlay, _, _ = overlay_setup
    overlay.active_path = []

    # Track if signal was emitted by connecting a mock
    signal_emitted = []
    overlay.action_selected.connect(lambda key: signal_emitted.append(key))

    overlay.hide_menu(execute=True)

    assert len(signal_emitted) == 0


def test_hide_menu_with_selection(overlay_setup):
    """Test hiding menu with selection emits correct signal"""
    overlay, _, _ = overlay_setup
    overlay.active_path = [2]

    # Track if signal was emitted
    signal_emitted = []
    overlay.action_selected.connect(lambda key: signal_emitted.append(key))

    overlay.hide_menu(execute=True)

    assert len(signal_emitted) == 1
    assert signal_emitted[0] == "s"  # South item key

    # Selection should be reset
    assert overlay.active_path == []


def test_hide_menu_without_execute(overlay_setup):
    """Test hiding menu without execute flag doesn't emit signal"""
    overlay, _, _ = overlay_setup
    overlay.active_path = [1]

    # Track if signal was emitted
    signal_emitted = []
    overlay.action_selected.connect(lambda key: signal_emitted.append(key))

    overlay.hide_menu(execute=False)

    assert len(signal_emitted) == 0


def test_show_menu_positioning(overlay_setup):
    """Test show_menu covers screen and maps center_pos correctly"""
    overlay, _, _ = overlay_setup

    expected_rect = QRect(0, 0, 1920, 1080)
    with patch("src.ui.overlay.QCursor.pos", return_value=QPoint(800, 600)):
        # Mock screen geometry
        mock_screen = MagicMock()
        mock_screen.geometry.return_value = expected_rect
        with (
            patch("PyQt6.QtWidgets.QApplication.primaryScreen", return_value=mock_screen),
            patch("PyQt6.QtGui.QGuiApplication.screenAt", return_value=mock_screen),
        ):
            overlay.show_menu()

            # Window should be size of the mocked screen
            geometry = overlay.geometry()
            # In some CI environments, setGeometry might be constrained by the actual display,
            # but we can at least verify our logic sets it correctly or check relative values.
            # However, since we mock screenAt and primaryScreen, Qt should ideally follow it.
            assert geometry.width() == expected_rect.width()
            assert geometry.height() == expected_rect.height()

            # center_pos should map directly to cursor since screen is at 0,0
            assert overlay.center_pos == QPoint(800, 600)


def test_show_menu_on_secondary_screen(overlay_setup):
    """Test show_menu on a secondary screen (e.g., screen at 1920,0)"""
    overlay, _, _ = overlay_setup

    screen_rect = QRect(1920, 0, 1920, 1080)
    with patch("src.ui.overlay.QCursor.pos", return_value=QPoint(2000, 100)):
        mock_screen = MagicMock()
        mock_screen.geometry.return_value = screen_rect
        with (
            patch("PyQt6.QtWidgets.QApplication.primaryScreen", return_value=mock_screen),
            patch("PyQt6.QtGui.QGuiApplication.screenAt", return_value=mock_screen),
        ):
            overlay.show_menu()

        # Window should be size of primary screen
        geometry = overlay.geometry()
        assert geometry.width() == screen_rect.width()
        assert geometry.height() == screen_rect.height()

        # center_pos = cursor - screen_rect.topLeft() = (2000,100) - (1920,0) = (80,100)
        assert overlay.center_pos == QPoint(80, 100)


def test_many_items(qapp):
    """Test overlay with many items (12)"""
    settings = AppSettings()
    many_items = [PieSlice(label=f"Item{i}", key=f"{i}", color="#FF0000") for i in range(12)]
    overlay = PieOverlay(many_items, settings)
    overlay.is_visible = True
    overlay.center_pos = QPoint(250, 250)

    # Each slice should be 30 degrees
    # Just verify it doesn't crash and can select items
    overlay.update_selection(QPoint(250, 150))  # North

    assert len(overlay.active_path) > 0
    assert overlay.active_path[0] >= 0
    assert overlay.active_path[0] < 12

    overlay.close()


def test_center_exited_signal_after_inner_zone(overlay_setup):
    """Test center_exited is emitted when dragged outside radius_inner after entering it"""
    overlay, _, _ = overlay_setup
    overlay.center_pos = QPoint(250, 250)

    # Move inside inner circle
    overlay.update_selection(QPoint(255, 255))

    # Track signal
    emissions = []
    overlay.center_exited.connect(lambda: emissions.append(True))

    # Move outside inner circle
    overlay.update_selection(QPoint(250, 150))

    assert len(emissions) == 1


def test_create_slice_path(overlay_setup, monkeypatch):
    """Test slice path creation logic with dummy center."""
    overlay, _, _ = overlay_setup

    overlay.show_menu()

    # We just need to ensure it returns a valid QPainterPath now.
    path = overlay._create_slice_path(0, 90, 50, 100)
    assert isinstance(path, QPainterPath)
    assert not path.isEmpty()


def test_center_hover_signals(overlay_setup):
    """Test center_hovered and center_exited signals"""
    overlay, _, _ = overlay_setup
    overlay.center_pos = QPoint(250, 250)

    if not hasattr(overlay, "center_hovered"):
        pytest.skip("center_hovered signal not yet implemented")

    signals = []
    overlay.center_hovered.connect(lambda: signals.append("hovered"))
    overlay.center_exited.connect(lambda: signals.append("exited"))

    # Initially outside inner radius
    overlay.update_selection(QPoint(350, 250))
    assert len(signals) == 0

    # Move inside inner radius (< 50)
    overlay.update_selection(QPoint(260, 250))  # 10px away
    assert len(signals) == 1
    assert signals[-1] == "hovered"

    # Move around inside inner radius, should not trigger again
    overlay.update_selection(QPoint(240, 250))
    assert len(signals) == 1

    # Move outside inner radius
    overlay.update_selection(QPoint(350, 250))
    assert len(signals) == 2
    assert signals[-1] == "exited"
