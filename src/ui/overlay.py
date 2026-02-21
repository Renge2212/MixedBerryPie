"""Pie menu overlay window.

Provides the visual pie menu interface with:
- Radial menu layout with customizable slices
- Mouse-based selection with visual feedback
- Smooth animations for show/hide
- Icon and label rendering
- Color-coded menu items
"""

import math
from typing import Any

from PyQt6.QtCore import QPoint, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QWidget

from src.core.config import AppSettings, PieSlice
from src.core.logger import get_logger
from src.core.utils import resolve_icon_path

logger = get_logger(__name__)


class PieOverlay(QWidget):
    """Transparent overlay widget for rendering the pie menu."""

    action_selected = pyqtSignal(str, str)  # key, action_type

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

        # Settings
        self.settings = settings or AppSettings()
        self.menu_items = menu_items or []

        # State
        self.selected_index: int = -1
        self.center_pos = QPoint(0, 0)
        self.is_visible = False

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
        self._micro_font: QFont | None = None

    def update_settings(self, settings: AppSettings) -> None:
        """Update overlay settings and recalculate dimensions.

        Args:
            settings: New application settings.
        """
        self.settings = settings
        self._update_dimensions()
        self._icon_cache.clear()  # Clear cache as icon size might have changed
        self._recalculate_paths() # Rebuild static paths
        self.update()

    def _update_dimensions(self) -> None:
        """Recalculate radius and sizes based on settings."""
        size = self.settings.overlay_size
        # Add padding for the pop-out animation (10px * 2 = 20px, plus safety)
        self.resize(size + 40, size + 40)
        self.center_pos = QPoint(self.width() // 2, self.height() // 2)

        self.radius_outer = size // 2
        self.radius_inner = int(self.radius_outer * 0.25)

        if self.settings.auto_scale_with_menu:
            # Scale icon and text proportionally to menu size (base: 400px)
            scale = size / 400.0
            self.icon_size = max(16, int(self.settings.icon_size * scale))
            self.text_size = max(7, int(self.settings.text_size * scale))
        else:
            self.icon_size = self.settings.icon_size
            self.text_size = self.settings.text_size

        # Initialize fonts
        self._item_font = QFont("Segoe UI")
        self._item_font.setBold(True)
        self._item_font.setPointSize(self.text_size)

        self._micro_font = QFont("Segoe UI", 8, QFont.Weight.Bold)

    def _recalculate_paths(self) -> None:
        """Pre-calculate and cache the QPainterPaths for all slices."""
        self._slice_paths_cache.clear()
        self._highlight_paths_cache.clear()

        num_items = len(self.menu_items)
        if num_items == 0:
            return

        angle_span = 360.0 / num_items
        for i in range(num_items):
            start_angle = -90 - (angle_span / 2) + (i * angle_span)

            # Base slice path
            base_path = self._create_slice_path(start_angle, angle_span, self.radius_outer)
            self._slice_paths_cache.append(base_path)

            # Highlight border path (slightly larger)
            hl_path = self._create_slice_path(start_angle, angle_span, self.radius_outer + 10)
            self._highlight_paths_cache.append(hl_path)

    def show_menu(self) -> None:
        """Show the overlay at the current mouse position with animation."""
        if not self.menu_items:
            logger.warning("No menu items to show")
            return

        logger.info(f"Show menu called. Animations enabled: {self.settings.show_animations}")

        cursor_pos = QCursor.pos()
        # Center the window on the cursor
        x = cursor_pos.x() - self.width() // 2
        y = cursor_pos.y() - self.height() // 2
        self.move(x, y)

        self.selected_index = -1
        self.is_visible = True

        # Ensure paths are calculated when showing
        if not self._slice_paths_cache or len(self._slice_paths_cache) != len(self.menu_items):
            self._recalculate_paths()

        if self.settings.show_animations:
            self.animation_scale = 0.0
            self.is_animating = True
            self.scale_timer.start()
        else:
            self.animation_scale = 1.0
            self.is_animating = False

        self.show()
        self.update()
        self._poll_timer.start()
        logger.debug(f"Overlay shown at {cursor_pos}")

    def hide_menu(self, execute: bool = False) -> None:
        """Hide the overlay and optionally execute the selected action.

        Args:
            execute: Whether to execute the selected item's action.
        """
        if not self.is_visible:
            return

        self.is_visible = False
        self._poll_timer.stop()
        self.hide()
        self.scale_timer.stop()

        if execute and self.selected_index != -1:
            item = self.menu_items[self.selected_index]
            # Emit signal instead of executing directly to decouple
            self.action_selected.emit(item.key, item.action_type)

        self.selected_index = -1

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

    def update_selection(self, pos):
        """Update selected item based on mouse position.

        Args:
            pos: Mouse position relative to the widget.
        """
        if not self.is_visible:
            return

        dx = pos.x() - self.center_pos.x()
        dy = pos.y() - self.center_pos.y()
        distance = math.sqrt(dx * dx + dy * dy)

        # Dead zone: inside the inner ring → clear selection
        if distance < self.radius_inner:
            self.selected_index = -1
            return

        # Outside outer radius is still valid — selection continues by angle direction
        # (no early return here)

        # Calculate angle
        angle = math.atan2(dy, dx)
        if angle < 0:
            angle += 2 * math.pi

        # Convert to degrees (0-360)
        degrees = math.degrees(angle)

        num_items = len(self.menu_items)
        if num_items == 0:
            return

        angle_per_item = 360 / num_items

        # Adjust degrees so 0 is Up to match drawing logic
        adj_degrees = (degrees + 90) % 360

        # Correct calculation:
        # We need to shift by half a slice to align index changes with boundaries
        index = int((adj_degrees + angle_per_item / 2) / angle_per_item) % num_items
        self.selected_index = index


    def paintEvent(self, event):
        """Paint the pie menu.

        Args:
            event: Paint event.
        """
        if not self.is_visible:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Apply scaling animation
        if self.is_animating:
            # Scale from center
            painter.translate(self.center_pos)
            painter.scale(self.animation_scale, self.animation_scale)
            painter.translate(-self.center_pos)

        num_items = len(self.menu_items)
        if num_items == 0:
            return

        angle_span = 360.0 / num_items

        for i, item in enumerate(self.menu_items):
            # Calculate angles
            # Start at -90 (top) and rotate clockwise
            # Center of first item should be at -90
            start_angle = -90 - (angle_span / 2) + (i * angle_span)

            # Draw Slice from cache if available
            if i < len(self._slice_paths_cache):
                path = self._slice_paths_cache[i]
            else:
                path = self._create_slice_path(start_angle, angle_span, self.radius_outer)

            color = QColor(item.color)
            # Make it slightly transparent for glass/overlay effect based on settings
            opacity_percent = getattr(self.settings, 'menu_opacity', 80)
            color.setAlpha(int(255 * opacity_percent / 100))

            is_selected = i == self.selected_index

            if is_selected:
                color = color.lighter(130)  # Highlight
                # Pop out effect could be done here by translating painter

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)

            # Draw Border if selected
            if self.selected_index == i:
                # Highlight selected item from cache if available
                if i < len(self._highlight_paths_cache):
                    path = self._highlight_paths_cache[i]
                else:
                    path = self._create_slice_path(angle_start=start_angle, angle_span=angle_span, radius=self.radius_outer + 10)

                painter.setBrush(QBrush(QColor(item.color)))
                pen_width = 2
                painter.setPen(
                    QPen(
                        QColor(255, 255, 255, 200),
                        pen_width,
                        Qt.PenStyle.SolidLine,
                    )
                )
                painter.drawPath(path)

            # Draw Label and Icon
            self._draw_item_content(painter, item, start_angle + angle_span / 2)

    def _create_slice_path(self, angle_start, angle_span, radius) -> QPainterPath:
        # Create painter path for a single pie slice
        path = QPainterPath()

        # Correct for Qt's CCW angle system: Qt uses CCW, we used CW logic
        qt_start_angle = -angle_start
        qt_span_angle = -angle_span

        # Outer arc
        rect_outer = QRectF(
            self.center_pos.x() - radius,
            self.center_pos.y() - radius,
            radius * 2,
            radius * 2,
        )
        path.arcMoveTo(rect_outer, qt_start_angle)
        path.arcTo(rect_outer, qt_start_angle, qt_span_angle)

        # Inner arc (drawn in reverse to close the shape correctly)
        rect_inner = QRectF(
            self.center_pos.x() - self.radius_inner,
            self.center_pos.y() - self.radius_inner,
            self.radius_inner * 2,
            self.radius_inner * 2,
        )
        qt_end_angle = qt_start_angle + qt_span_angle
        path.arcTo(rect_inner, qt_end_angle, -qt_span_angle)

        path.closeSubpath()
        return path

    def _draw_item_content(self, painter: QPainter, item: PieSlice, mid_angle: float) -> None:
        """Draw icon and label for the item."""
        # Calculate center position of the content
        rad_mid = (self.radius_inner + self.radius_outer) / 2
        rad_angle = math.radians(mid_angle)

        # Polar to Cartesian
        cx = self.center_pos.x() + rad_mid * math.cos(rad_angle)
        cy = self.center_pos.y() + rad_mid * math.sin(rad_angle)

        # Draw Icon
        icon_size = self.icon_size

        # If item has an icon path, load and draw it
        if item.icon_path:
            # Resolve path (handles relative paths like 'icons/pencil.svg')
            resolved_path = resolve_icon_path(item.icon_path)
            if not resolved_path:
                return

            # Cache key
            cache_key = (resolved_path, icon_size)

            # Check if SVG or standard image
            if resolved_path.lower().endswith('.svg'):
                if cache_key not in self._icon_cache:
                    pixmap = QPixmap(icon_size, icon_size)
                    pixmap.fill(Qt.GlobalColor.transparent)
                    renderer = QSvgRenderer(resolved_path)
                    if renderer.isValid():
                        svg_painter = QPainter(pixmap)
                        # High quality render
                        svg_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                        svg_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                        renderer.render(svg_painter)
                        svg_painter.end()
                        self._icon_cache[cache_key] = pixmap
                    else:
                        self._icon_cache[cache_key] = QPixmap()

                pixmap = self._icon_cache[cache_key]
                if not pixmap.isNull():
                    painter.drawPixmap(
                        int(cx - icon_size / 2),
                        int(cy - icon_size / 2 - 10),
                        pixmap
                    )
            else:
                # Handle Raster
                if cache_key not in self._icon_cache:
                    pixmap = QIcon(resolved_path).pixmap(int(icon_size), int(icon_size))
                    self._icon_cache[cache_key] = pixmap

                pixmap = self._icon_cache[cache_key]
                if not pixmap.isNull():
                    painter.drawPixmap(
                        int(cx - icon_size / 2),
                        int(cy - icon_size / 2 - 10),
                        pixmap
                    )

        # Draw Label
        painter.setPen(Qt.GlobalColor.white)
        if self._item_font:
            painter.setFont(self._item_font)
        else:
            font = QFont("Segoe UI")
            font.setBold(True)
            font.setPointSize(self.text_size)
            painter.setFont(font)

        # Calculate text position
        if item.icon_path:
            # Text below icon
            text_rect = QRectF(cx - 60, cy + icon_size / 2 - 5, 120, 40)
        else:
            # Text centered vertically (no icon)
            text_rect = QRectF(cx - 60, cy - 20, 120, 40)

        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            item.label,
        )
