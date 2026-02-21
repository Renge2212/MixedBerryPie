from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QPoint, QRect

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
        PieSlice(label="West", key="w", color="#FFFF00")
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
    assert overlay.selected_index == -1
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
    assert empty_overlay.selected_index == -1

    empty_overlay.close()

def test_single_item(qapp):
    """Test overlay with single item"""
    settings = AppSettings()
    single_overlay = PieOverlay([PieSlice(label="Only", key="o", color="#FF0000")], settings)
    single_overlay.is_visible = True

    # Any position outside inner radius should select item 0
    single_overlay.center_pos = QPoint(250, 250)
    single_overlay.update_selection(QPoint(350, 250))  # Right of center
    assert single_overlay.selected_index == 0

    single_overlay.close()

def test_selection_inside_inner_radius(overlay_setup):
    overlay, _, _ = overlay_setup
    overlay.center_pos = QPoint(250, 250)

    # Position very close to center (within inner radius of 20)
    # Inner radius is 62 actually per test_initialization
    overlay.update_selection(QPoint(255, 255))
    assert overlay.selected_index == -1

def test_selection_angle_calculation_north(overlay_setup):
    overlay, _, _ = overlay_setup
    overlay.center_pos = QPoint(250, 250)

    # Position directly above center (North)
    overlay.update_selection(QPoint(250, 150))  # 100 pixels up
    assert overlay.selected_index == 0

def test_selection_angle_calculation_east(overlay_setup):
    overlay, _, _ = overlay_setup
    overlay.center_pos = QPoint(250, 250)

    # Position directly right of center (East)
    overlay.update_selection(QPoint(350, 250))  # 100 pixels right
    assert overlay.selected_index == 1

def test_selection_angle_calculation_south(overlay_setup):
    overlay, _, _ = overlay_setup
    overlay.center_pos = QPoint(250, 250)

    # Position directly below center (South)
    overlay.update_selection(QPoint(250, 350))  # 100 pixels down
    assert overlay.selected_index == 2

def test_selection_angle_calculation_west(overlay_setup):
    overlay, _, _ = overlay_setup
    overlay.center_pos = QPoint(250, 250)

    # Position directly left of center (West)
    overlay.update_selection(QPoint(150, 250))  # 100 pixels left
    assert overlay.selected_index == 3

def test_selection_with_six_items(qapp):
    """Test selection with 6 items (60 degrees each)"""
    settings = AppSettings()
    six_items = [
        PieSlice(label=f"Item{i}", key=f"{i}", color="#FF0000")
        for i in range(6)
    ]
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
        assert overlay.selected_index == expected_index, f"Position ({x}, {y}) should select item {expected_index}"

    overlay.close()

def test_hide_menu_without_selection(overlay_setup):
    """Test hiding menu without selection doesn't emit signal"""
    overlay, _, _ = overlay_setup
    overlay.selected_index = -1

    # Track if signal was emitted by connecting a mock
    signal_emitted = []
    overlay.action_selected.connect(lambda key: signal_emitted.append(key))

    overlay.hide_menu(execute=True)

    assert len(signal_emitted) == 0

def test_hide_menu_with_selection(overlay_setup):
    """Test hiding menu with selection emits correct signal"""
    overlay, _, _ = overlay_setup
    overlay.selected_index = 2

    # Track if signal was emitted
    signal_emitted = []
    overlay.action_selected.connect(lambda key: signal_emitted.append(key))

    overlay.hide_menu(execute=True)

    assert len(signal_emitted) == 1
    assert signal_emitted[0] == "s"  # South item key

    # Selection should be reset
    assert overlay.selected_index == -1

def test_hide_menu_without_execute(overlay_setup):
    """Test hiding menu without execute flag doesn't emit signal"""
    overlay, _, _ = overlay_setup
    overlay.selected_index = 1

    # Track if signal was emitted
    signal_emitted = []
    overlay.action_selected.connect(lambda key: signal_emitted.append(key))

    overlay.hide_menu(execute=False)

    assert len(signal_emitted) == 0

def test_show_menu_positioning(overlay_setup):
    """Test show_menu covers screen and maps center_pos correctly"""
    overlay, _, _ = overlay_setup

    with patch('src.ui.overlay.QCursor.pos', return_value=QPoint(800, 600)):
        # Mock screen geometry
        mock_screen = MagicMock()
        mock_screen.geometry.return_value = QRect(0, 0, 2000, 2000)
        with patch('PyQt6.QtWidgets.QApplication.screenAt', return_value=mock_screen):
            overlay.show_menu()

            # Window should be overlay_size (400) + padding (40) = 440
            geometry = overlay.geometry()
            assert geometry.width() == 440
            assert geometry.height() == 440

            # center_pos should be center of the widget (440/2 = 220)
            assert overlay.center_pos == QPoint(220, 220)

def test_show_menu_on_secondary_screen(overlay_setup):
    """Test show_menu covers the correct screen when using multiple monitors"""
    overlay, _, _ = overlay_setup

    # Cursor on secondary screen (offset by 1920)
    with patch('src.ui.overlay.QCursor.pos', return_value=QPoint(2000, 100)):
        # Mock screen geometry
        mock_screen = MagicMock()
        mock_screen.geometry.return_value = QRect(1920, 0, 1920, 1080)
        with patch('PyQt6.QtWidgets.QApplication.screenAt', return_value=mock_screen):
            overlay.show_menu()

            # Window should be overlay_size (400) + padding (40) = 440
            geometry = overlay.geometry()
            # Cursor at 2000, 100. Window centered: 2000 - (440/2) = 2000 - 220 = 1780
            assert geometry.x() == 1780
            assert geometry.width() == 440

            # center_pos should be center of widget (440/2 = 220)
            assert overlay.center_pos == QPoint(220, 220)

def test_many_items(qapp):
    """Test overlay with many items (12)"""
    settings = AppSettings()
    many_items = [
        PieSlice(label=f"Item{i}", key=f"{i}", color="#FF0000")
        for i in range(12)
    ]
    overlay = PieOverlay(many_items, settings)
    overlay.is_visible = True
    overlay.center_pos = QPoint(250, 250)

    # Each slice should be 30 degrees
    # Just verify it doesn't crash and can select items
    overlay.update_selection(QPoint(250, 150))  # North

    assert overlay.selected_index >= 0
    assert overlay.selected_index < 12

    overlay.close()
