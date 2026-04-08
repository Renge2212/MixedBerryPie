"""Pie menu overlay window.

Provides the visual pie menu interface with:
- Radial menu layout with customizable slices
- Mouse-based selection with visual feedback
- Smooth animations for show/hide
- Icon and label rendering
- Color-coded menu items
"""

import ctypes
import math
import sys
from typing import Any

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
)
from PyQt6.QtWidgets import QApplication, QWidget

from src.core.config import AppSettings, PieSlice
from src.core.logger import get_logger
from src.ui.components.pie_renderer import MAX_FAN_SPAN_DEG, PieRenderMixin

logger = get_logger(__name__)


class PieOverlay(QWidget, PieRenderMixin):
    """Transparent overlay widget for rendering the pie menu."""

    action_selected = pyqtSignal(str, str)  # key, action_type
    slice_exited = pyqtSignal(object, int)  # PieSlice, index
    center_hovered = pyqtSignal()
    center_exited = pyqtSignal()

    def __init__(
        self, menu_items: list[PieSlice] | None = None, settings: AppSettings | None = None
    ) -> None:
        """Initialize the overlay.

        Args:
            menu_items: List of pie slices to display.
            settings: Application settings.
        """
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # We don't want it to steal focus if clicked globally
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        # Settings
        self.settings = settings or AppSettings()
        self.menu_items = menu_items or []

        # State
        self.active_path: list[
            int
        ] = []  # List of indices representing the selected path [root_idx, child_idx, ...]
        self.center_pos = QPoint(0, 0)
        self.is_visible = False
        self._is_in_center = False

        # Animation state
        self.scale_timer = QTimer(self)
        self.scale_timer.timeout.connect(self._update_scale_animation)
        self.scale_timer.setInterval(16)  # ~60 FPS
        self.animation_scale = 0.0
        self.is_animating = False
        self.scale_target = 1.0

        # Constants (recalculated on settings update)
        self._update_dimensions()

        # Input handling
        self.setMouseTracking(True)

        # Poll global cursor position so selection works outside widget bounds
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(16)  # ~60 FPS
        self._poll_timer.timeout.connect(self._poll_cursor)

        # Cache for icons to avoid reloading every frame
        self._icon_cache: dict[tuple[str, int], Any] = {}

        # Cache for paths and fonts
        self._slice_paths_cache: list[QPainterPath] = []
        self._highlight_paths_cache: list[QPainterPath] = []
        self._item_font: QFont | None = None

        # Initialize the widget to cover the primary screen and show it.
        # Its visibility will be controlled by the `is_visible` flag.
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        self.show()

    def update_settings(self, settings: AppSettings) -> None:
        """Update overlay settings and recalculate dimensions.

        Args:
            settings: New application settings.
        """
        self.settings = settings
        self._update_dimensions()
        self._icon_cache.clear()  # Clear cache as icon size might have changed
        self._recalculate_paths()  # Rebuild static paths
        self.update()

    def _get_max_depth(self, items: list[PieSlice], current_depth: int = 0) -> int:
        """Calculate the maximum depth of the nested menu structure."""
        max_d = current_depth
        for item in items:
            subs = getattr(item, "submenu_items", None)
            if subs:
                d = self._get_max_depth(subs, current_depth + 1)
                max_d = max(max_d, d)
        return max_d

    def _update_dimensions(self) -> None:
        """Recalculate radius and sizes based on settings."""
        size = self.settings.overlay_size
        self.radius_outer = size // 2
        self.radius_inner = int(self.radius_outer * 0.25)
        # Thickness of additional concentric rings for submenus
        self.ring_thickness = int(self.radius_outer * 0.5)
        # Gap between rings to prevent overlap with selection highlight (10px highlight + 5px extra)
        self.ring_gap = 15

        if self.settings.auto_scale_with_menu:
            # Scale icon and text proportionally to menu size (base: 400px)
            scale = size / 400.0
            self.icon_size = max(16, int(self.settings.icon_size * scale))
            self.text_size = max(7, int(self.settings.text_size * scale))
        else:
            self.icon_size = self.settings.icon_size
            self.text_size = self.settings.text_size

        # Initialize fonts (using configured font)
        self._item_font = QFont(self.settings.font_family)
        self._item_font.setBold(True)
        self._item_font.setPointSize(self.text_size)

        self._micro_font = QFont(self.settings.font_family, 8, QFont.Weight.Bold)

    def _recalculate_paths(self) -> None:
        """Obsolete: Paths are now dynamically generated in _draw_layer to support concentric rings and submenus."""
        pass

    def show_menu(self) -> None:
        """Show the overlay at the current mouse position with animation."""
        if not self.menu_items:
            logger.warning("No menu items to show")
            return

        logger.info(f"Show menu called. Animations enabled: {self.settings.show_animations}")

        # Update dimensions and get screen geometry
        self._update_dimensions()

        # Ensure the overlay covers the correct screen containing the cursor
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos)
        if not screen:
            screen = QApplication.primaryScreen()

        if screen:
            screen_rect = screen.geometry()
            if self.geometry() != screen_rect:
                self.setGeometry(screen_rect)

            self.center_pos = QPoint(
                cursor_pos.x() - screen_rect.x(), cursor_pos.y() - screen_rect.y()
            )

        self.active_path = []
        self.is_visible = True
        self._is_in_center = False

        if self.settings.show_animations:
            self.animation_scale = 0.0
            self.is_animating = True
            self.scale_timer.start()
        else:
            self.animation_scale = 1.0
            self.is_animating = False

        # Make sure the window is visible at the OS level
        if not self.isVisible():
            self.show()

        # Force the window to the topmost Z-order position.
        # WindowStaysOnTopHint can lose effect over time on Windows when other
        # topmost windows shuffle the Z-order. Re-apply via Win32 SetWindowPos.
        self.raise_()
        if sys.platform == "win32":
            hwnd = int(self.winId())
            hwnd_topmost = -1
            swp_nomove = 0x0002
            swp_nosize = 0x0001
            swp_noactivate = 0x0010
            swp_showwindow = 0x0040
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                hwnd_topmost,
                0,
                0,
                0,
                0,
                swp_nomove | swp_nosize | swp_noactivate | swp_showwindow,
            )

        # Trigger a Qt paint event
        self.update()

        self._poll_timer.start()
        logger.debug(f"Menu internal state shown at {self.center_pos}")

    def hide_menu(self, execute: bool = False) -> None:
        """Hide the overlay and optionally execute the selected action.

        Args:
            execute: Whether to execute the selected item's action.
        """
        if not self.is_visible:
            return

        self.is_visible = False
        self._poll_timer.stop()
        self.scale_timer.stop()

        # Clear the menu visually but keep the transparent window alive
        self.update()

        if execute and self.active_path:
            # Find the actual executed item by traversing the active path
            item: PieSlice | None = None
            current_list = self.menu_items
            for idx in self.active_path:
                if 0 <= idx < len(current_list):
                    item = current_list[idx]
                    current_list = (
                        item.submenu_items if getattr(item, "submenu_items", None) else []
                    )
                else:
                    item = None
                    break

            if item:
                self.action_selected.emit(item.key, item.action_type)

        self.active_path = []

    def _update_scale_animation(self) -> None:
        """Update scale factor for entry animation."""
        step = 0.15  # Faster animation (approx 100ms)
        if self.animation_scale < self.scale_target:
            self.animation_scale = min(self.scale_target, self.animation_scale + step)
            self.update()
        else:
            self.scale_timer.stop()
            self.is_animating = False

    def _poll_cursor(self) -> None:
        """Poll global cursor position and update selection (handles outside-widget movement)."""
        if not self.is_visible:
            return
        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        self.update_selection(local_pos)
        self.update()

    def mouseMoveEvent(self, event: Any) -> None:
        """Handle mouse move events (inside widget bounds).

        Args:
            event: Mouse event object
        """
        # _poll_cursor handles this too, but keep for responsiveness
        self.update_selection(event.pos())
        self.update()

    def _calc_polar(self, pos) -> tuple[float, float]:
        """Convert mouse position to (distance, adjusted_degrees) from center.

        Returns adjusted degrees where 0 = Up, increasing clockwise.
        """
        dx = pos.x() - self.center_pos.x()
        dy = pos.y() - self.center_pos.y()
        distance = math.sqrt(dx * dx + dy * dy)
        angle = math.atan2(dy, dx)
        if angle < 0:
            angle += 2 * math.pi
        adj_degrees = (math.degrees(angle) + 90) % 360
        return distance, adj_degrees

    def _determine_target_layer(self, distance: float) -> int:
        """Determine the deepest pie layer the cursor is over based on distance."""
        if distance <= self.radius_outer:
            return 0
        return 1 + int((distance - self.radius_outer) / (self.ring_thickness + self.ring_gap))

    def _is_within_fan(
        self, adj_degrees: float, center_angle: float, fan_span: float
    ) -> tuple[bool, float]:
        """Check if adj_degrees falls within a fan centered at center_angle.

        Returns (is_within, relative_angle_within_fan).
        """
        s_adj = (center_angle - fan_span / 2 + 90) % 360
        r_angle = (adj_degrees - s_adj) % 360
        if r_angle > 180 and fan_span <= MAX_FAN_SPAN_DEG:
            r_angle -= 360
        return (0 <= r_angle <= fan_span), r_angle

    def _should_lock_to_submenu(
        self,
        locked_idx: int,
        items: list[PieSlice],
        adj_degrees: float,
        depth: int,
        path: list[int],
    ) -> bool:
        """Check if the cursor is within the locked item's submenu fan."""
        if locked_idx < 0 or locked_idx >= len(items):
            return False
        sub_items = getattr(items[locked_idx], "submenu_items", [])
        if not sub_items:
            return False
        c_angle = self._get_slice_center_angle(depth, [*path, locked_idx])
        sub_count = len(sub_items)
        fan_span = (MAX_FAN_SPAN_DEG / max(1, sub_count)) * sub_count
        within, _ = self._is_within_fan(adj_degrees, c_angle, fan_span)
        return within

    def update_selection(self, pos):
        """Update selected item based on mouse position.

        Args:
            pos: Mouse position relative to the widget.
        """
        if not self.is_visible or not self.menu_items:
            return

        distance, adj_degrees = self._calc_polar(pos)

        # Dead zone: inside the inner ring
        if distance < self.radius_inner:
            if getattr(self, "_is_in_center", False) is False:
                self._is_in_center = True
                self.center_hovered.emit()
            self.active_path = []
            return

        if getattr(self, "_is_in_center", False) is True:
            self._is_in_center = False
            self.center_exited.emit()

        raw_target_layer = self._determine_target_layer(distance)

        new_path: list[int] = []
        current_items = self.menu_items

        for layer in range(raw_target_layer + 1):
            if not current_items:
                break

            num_items = len(current_items)
            angle_span = 360.0 / num_items if layer == 0 else MAX_FAN_SPAN_DEG / max(1, num_items)

            if layer == 0:
                hover_idx = int((adj_degrees + angle_span / 2) / angle_span) % num_items
                locked_idx = self.active_path[0] if len(self.active_path) > 0 else -1
                use_lock = (
                    locked_idx != -1
                    and raw_target_layer > 0
                    and self._should_lock_to_submenu(locked_idx, current_items, adj_degrees, 0, [])
                )
                current_idx = locked_idx if use_lock else hover_idx
            else:
                c_angle = self._get_slice_center_angle(layer - 1, new_path)
                t_span = angle_span * num_items
                within, r_angle = self._is_within_fan(adj_degrees, c_angle, t_span)

                if not within:
                    break  # Cursor outside this fan — stop at parent layer

                hover_idx = min(int(r_angle / angle_span), num_items - 1)
                locked_idx = self.active_path[layer] if len(self.active_path) > layer else -1
                use_lock = (
                    locked_idx != -1
                    and raw_target_layer > layer
                    and self._should_lock_to_submenu(
                        locked_idx, current_items, adj_degrees, layer, new_path
                    )
                )
                current_idx = locked_idx if use_lock else hover_idx

            new_path.append(current_idx)
            current_items = getattr(current_items[current_idx], "submenu_items", [])

        self.active_path = new_path

    def paintEvent(self, event):
        """Paint the pie menu.

        Args:
            event: Paint event.
        """
        if not self.is_visible:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 0. Clear screen completely (fixes residual images/artifacts when translucent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # 1. Background Dimming (fill entire widget/screen)
        if self.settings.dim_background:
            # We want a subtle dark overlay over everything before drawing the menu
            painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        # Apply scaling animation
        if self.is_animating:
            # Scale from center
            painter.translate(self.center_pos)
            painter.scale(self.animation_scale, self.animation_scale)
            painter.translate(-self.center_pos)

        num_items = len(self.menu_items)
        if num_items == 0:
            return

        # Draw layers in three passes to ensure labels are always on top of icons
        # Pass 1: Slice backgrounds
        self._draw_layer(
            painter, 0, self.menu_items, self.active_path, phase="background", alpha_mod=1.0
        )
        # Pass 2: Icons only
        self._draw_layer(
            painter, 0, self.menu_items, self.active_path, phase="icons", alpha_mod=1.0
        )
        # Pass 3: Labels on top of everything
        self._draw_layer(
            painter, 0, self.menu_items, self.active_path, phase="labels", alpha_mod=1.0
        )

    def _draw_item_content(
        self,
        painter: QPainter,
        item: PieSlice,
        index: int,
        total: int,
        mid_angle: float,
        rad_inner: float,
        rad_outer: float,
    ) -> None:
        """Draw icon and label (legacy single-pass helper)."""
        self._draw_item_icon(painter, item, index, total, mid_angle, rad_inner, rad_outer)
        self._draw_item_label(painter, item, index, total, mid_angle, rad_inner, rad_outer)
