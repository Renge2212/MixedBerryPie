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
    QGuiApplication,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication, QWidget

from src.core.config import COLOR_PRESETS, AppSettings, PieSlice
from src.core.logger import get_logger
from src.core.utils import resolve_icon_path

logger = get_logger(__name__)


class PieOverlay(QWidget):
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
        self._micro_font: QFont | None = None

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
                if max_d < d:
                    max_d = d
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

    def update_selection(self, pos):
        """Update selected item based on mouse position.

        Args:
            pos: Mouse position relative to the widget.
        """
        if not self.is_visible or not self.menu_items:
            return

        dx = pos.x() - self.center_pos.x()
        dy = pos.y() - self.center_pos.y()
        distance = math.sqrt(dx * dx + dy * dy)

        # Dead zone: inside the inner ring → clear selection
        if distance < self.radius_inner:
            if getattr(self, "_is_in_center", False) is False:
                self._is_in_center = True
                self.center_hovered.emit()
            self.active_path = []
            return

        if getattr(self, "_is_in_center", False) is True:
            self._is_in_center = False
            self.center_exited.emit()

        # Calculate angle
        angle = math.atan2(dy, dx)
        if angle < 0:
            angle += 2 * math.pi

        # Convert to degrees (0-360)
        degrees = math.degrees(angle)
        # Adjust degrees so 0 is Up to match drawing logic
        adj_degrees = (degrees + 90) % 360

        # Determine how deep we are based on distance
        # Layer 0: radius_inner to radius_outer
        # Layer 1: radius_outer to radius_outer + 1*ring_thickness
        # Layer 2: radius_outer + 1*ring_thickness to radius_outer + 2*ring_thickness ...

        # Base target layer determined by raw distance
        raw_target_layer = 0
        if distance > self.radius_outer:
            raw_target_layer = 1 + int(
                (distance - self.radius_outer) / (self.ring_thickness + self.ring_gap)
            )

        new_path: list[int] = []
        current_items = self.menu_items

        for layer in range(raw_target_layer + 1):
            if not current_items:
                break

            num_items = len(current_items)
            angle_span = 360.0 / num_items if layer == 0 else 180.0 / max(1, num_items)

            if layer == 0:
                hover_idx = int((adj_degrees + angle_span / 2) / angle_span) % num_items

                locked_idx = self.active_path[0] if len(self.active_path) > 0 else -1
                use_lock = False

                if locked_idx != -1 and locked_idx < num_items and raw_target_layer > 0:
                    locked_item = current_items[locked_idx]
                    sub_items = getattr(locked_item, "submenu_items", [])
                    if sub_items:
                        c_angle = self._get_slice_center_angle(0, [locked_idx])
                        sub_count = len(sub_items)
                        t_span = (180.0 / max(1, sub_count)) * sub_count
                        s_angle = c_angle - (t_span / 2)
                        s_adj = (s_angle + 90) % 360
                        r_angle = (adj_degrees - s_adj) % 360
                        if r_angle > 180 and t_span <= 180:
                            r_angle -= 360
                        if 0 <= r_angle <= t_span:
                            use_lock = True

                current_idx = locked_idx if use_lock else hover_idx
            else:
                c_angle = self._get_slice_center_angle(layer - 1, new_path)
                t_span = angle_span * num_items
                s_angle = c_angle - (t_span / 2)
                s_adj = (s_angle + 90) % 360
                r_angle = (adj_degrees - s_adj) % 360
                if r_angle > 180 and t_span <= 180:
                    r_angle -= 360

                if 0 <= r_angle <= t_span:
                    hover_idx = int(r_angle / angle_span)
                    if hover_idx >= num_items:
                        hover_idx = num_items - 1
                else:
                    # Cursor is completely outside this fan!
                    # Stop adding to path, leaving the selection at the parent layer.
                    break

                locked_idx = self.active_path[layer] if len(self.active_path) > layer else -1
                use_lock = False

                if locked_idx != -1 and locked_idx < num_items and raw_target_layer > layer:
                    locked_item = current_items[locked_idx]
                    sub_items = getattr(locked_item, "submenu_items", [])
                    if sub_items:
                        c_angle_next = self._get_slice_center_angle(layer, [*new_path, locked_idx])
                        sub_count = len(sub_items)
                        t_span_next = (180.0 / max(1, sub_count)) * sub_count
                        s_angle_next = c_angle_next - (t_span_next / 2)
                        s_adj_next = (s_angle_next + 90) % 360
                        r_angle_next = (adj_degrees - s_adj_next) % 360
                        if r_angle_next > 180 and t_span_next <= 180:
                            r_angle_next -= 360
                        if 0 <= r_angle_next <= t_span_next:
                            use_lock = True

                current_idx = locked_idx if use_lock else hover_idx

            new_path.append(current_idx)
            current_items = getattr(current_items[current_idx], "submenu_items", [])

        self.active_path = new_path

    def _get_slice_center_angle(self, depth: int, path: list[int]) -> float:
        """Calculate the absolute center angle (in degrees, 0=Up) of a specific slice at depth."""
        if not path or depth < 0 or depth >= len(path):
            return 0.0

        # Root layer
        num_root = len(self.menu_items)
        if num_root == 0:
            return 0.0
        root_span = 360.0 / num_root

        # Center of 0th item starts at -90
        center = -90.0 + (path[0] * root_span)

        if depth == 0:
            return center

        # Traverse down manually to calculate offsets
        current_list = (
            self.menu_items[path[0]].submenu_items
            if getattr(self.menu_items[path[0]], "submenu_items", None)
            else []
        )
        for depth_idx in range(1, depth + 1):
            if not current_list:
                break
            num_children = len(current_list)
            # Fan span logic
            fan_span = min(180.0, 60.0 * num_children)
            slice_span = fan_span / num_children

            # The fan is centered exactly on the previous center
            start_angle = center - (fan_span / 2)
            # The center of the specific child
            child_center = start_angle + (path[depth_idx] * slice_span) + (slice_span / 2)

            center = child_center
            current_list = (
                current_list[path[depth_idx]].submenu_items
                if getattr(current_list[path[depth_idx]], "submenu_items", None)
                else []
            )

        return center % 360

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
        self._draw_layer(painter, 0, self.menu_items, self.active_path, phase="background")
        # Pass 2: Icons only
        self._draw_layer(painter, 0, self.menu_items, self.active_path, phase="icons")
        # Pass 3: Labels on top of everything
        self._draw_layer(painter, 0, self.menu_items, self.active_path, phase="labels")

    def _draw_layer(
        self,
        painter: QPainter,
        depth: int,
        items: list[PieSlice],
        path: list[int],
        phase: str = "both",
    ):
        """Recursively draw a layer of the pie menu."""
        if not items:
            return

        num_items = len(items)
        # Root is 360, children fan out up to 180 depending on count
        angle_span = 360.0 / num_items if depth == 0 else min(180.0, 60.0 * num_items) / num_items

        # Calculate start angle for this layer
        if depth == 0:
            start_angle_base = -90 - (angle_span / 2)  # First item centered at -90 (Up)
        else:
            center_angle_of_parent = self._get_slice_center_angle(depth - 1, path)
            total_fan_span = angle_span * num_items
            start_angle_base = center_angle_of_parent - (total_fan_span / 2)

        # Radii for this layer
        if depth == 0:
            rad_inner = self.radius_inner
            rad_outer = self.radius_outer
        else:
            rad_inner = (
                self.radius_outer + (depth - 1) * self.ring_thickness + (depth * self.ring_gap)
            )
            rad_outer = rad_inner + self.ring_thickness

        # The selected index at this depth (if any)
        selected_idx = path[depth] if depth < len(path) else -1

        for i, item in enumerate(items):
            start_angle = start_angle_base + (i * angle_span)

            is_selected = i == selected_idx

            # Make selected slice slightly larger
            slice_rad_inner = rad_inner
            slice_rad_outer = rad_outer
            if is_selected:
                slice_rad_outer += 8  # Pop outwards
                slice_rad_inner -= 4  # Pop inwards slightly

            # Create Modern Pizza slice path with a constant pixel gap
            path_obj = self._create_slice_path(
                start_angle, angle_span, slice_rad_inner, slice_rad_outer, gap_px=6.0
            )

            # Determine effective color
            effective_color_str = self._get_effective_color(item, i, num_items)
            base_color = QColor(effective_color_str)

            # Use original opacity from settings
            opacity_percent = self.settings.menu_opacity
            base_color.setAlpha(int(255 * opacity_percent / 100))

            # 2. Slice Fill
            if phase in ("both", "background"):
                if is_selected:
                    # Selected: Brighter fill
                    fill_color = QColor(effective_color_str).lighter(130)
                    fill_color.setAlpha(int(255 * opacity_percent / 100))
                    painter.fillPath(path_obj, QBrush(fill_color))

                    # Glow/Border outline in the item's color
                    glow_color = QColor(effective_color_str)
                    glow_color.setAlpha(200)
                    glow_pen = QPen(glow_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                    glow_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.strokePath(path_obj, glow_pen)
                else:
                    # Unselected: Original item color
                    painter.fillPath(path_obj, QBrush(base_color))

            # 3. Draw Label and Icon
            if phase in ("both", "content", "icons"):
                self._draw_item_icon(
                    painter, item, i, num_items, start_angle + angle_span / 2, rad_inner, rad_outer
                )
            if phase in ("both", "content", "labels"):
                self._draw_item_label(
                    painter, item, i, num_items, start_angle + angle_span / 2, rad_inner, rad_outer
                )

        # Recursively draw the next layer if an item is selected and has submenus
        if selected_idx != -1 and selected_idx < num_items:
            selected_item = items[selected_idx]
            if getattr(selected_item, "submenu_items", None):
                self._draw_layer(painter, depth + 1, selected_item.submenu_items, path, phase)

    def _create_slice_path(
        self,
        angle_start: float,
        angle_span: float,
        rad_inner: float,
        rad_outer: float,
        gap_px: float = 0.0,
    ) -> QPainterPath:
        """Create painter path for a single pie slice with a constant pixel gap between slices."""
        if angle_span <= 0:
            angle_span = 0.1

        # Calculate angle reductions based on the desired physical pixel gap at both inner and outer radii
        # arc_length = radius * theta(radians) => theta = arc_length / radius
        # We halve the gap_px because each adjacent slice takes away half the gap
        half_gap = gap_px / 2.0

        # Guard against zero or extremely small radii DivisionByZero
        safe_rad_outer = max(1.0, rad_outer)
        safe_rad_inner = max(1.0, rad_inner)

        # Calculate angle reduction in degrees
        angle_reduce_outer = math.degrees(half_gap / safe_rad_outer)
        angle_reduce_inner = math.degrees(half_gap / safe_rad_inner)

        # If the gap is so large it consumes the whole slice, clamp it so the slice is at least 1 degree wide
        max_reduction = (angle_span - 1.0) / 2.0
        if max_reduction < 0:
            max_reduction = 0

        angle_reduce_outer = min(angle_reduce_outer, max_reduction)
        angle_reduce_inner = min(angle_reduce_inner, max_reduction)

        # Define the exact precise angles for the inner and outer arcs
        start_outer = angle_start + angle_reduce_outer
        span_outer = angle_span - (angle_reduce_outer * 2)

        start_inner = angle_start + angle_reduce_inner
        span_inner = angle_span - (angle_reduce_inner * 2)

        path = QPainterPath()

        # Correct for Qt's CCW angle system: Qt uses CCW, we used CW logic
        qt_start_outer = -start_outer
        qt_span_outer = -span_outer

        qt_start_inner = -start_inner
        qt_span_inner = -span_inner

        # Outer arc
        rect_outer = QRectF(
            self.center_pos.x() - rad_outer,
            self.center_pos.y() - rad_outer,
            rad_outer * 2,
            rad_outer * 2,
        )
        path.arcMoveTo(rect_outer, qt_start_outer)
        path.arcTo(rect_outer, qt_start_outer, qt_span_outer)

        # Inner arc (drawn in reverse to close the shape correctly)
        rect_inner = QRectF(
            self.center_pos.x() - rad_inner,
            self.center_pos.y() - rad_inner,
            rad_inner * 2,
            rad_inner * 2,
        )
        qt_end_inner = qt_start_inner + qt_span_inner

        # Draw a straight line from the end of the outer arc to the start of the inner arc
        # (Qt's arcTo automatically draws a line from the current position to the start of the new arc if needed,
        # so calling arcTo directly is fine)
        path.arcTo(rect_inner, qt_end_inner, -qt_span_inner)

        path.closeSubpath()
        return path

    def _get_effective_color(self, item: PieSlice, index: int, total: int) -> str:
        """Get the color to use for a slice based on current color mode."""
        mode = self.settings.color_mode
        if mode == "unified":
            return self.settings.unified_color
        elif mode == "preset":
            palette = COLOR_PRESETS.get(self.settings.selected_preset)
            if not palette:
                palette = self.settings.custom_presets.get(self.settings.selected_preset, [])

            if palette:
                color_idx = index % len(palette)
                # Adjacency fix for circular menus: if last item matches first item (index 0), shift it
                if total > 1 and index == total - 1 and color_idx == 0 and len(palette) > 1:
                    color_idx = (color_idx + 1) % len(palette)
                return palette[color_idx]
        return item.color

    def _draw_item_icon(
        self,
        painter: QPainter,
        item: PieSlice,
        index: int,
        total: int,
        mid_angle: float,
        rad_inner: float,
        rad_outer: float,
    ) -> None:
        """Draw the icon for a pie slice."""
        if not item.icon_path:
            return

        rad_mid = (rad_inner + rad_outer) / 2
        rad_angle = math.radians(mid_angle)
        cx = self.center_pos.x() + rad_mid * math.cos(rad_angle)
        cy = self.center_pos.y() + rad_mid * math.sin(rad_angle)

        icon_size = self.icon_size
        resolved_path = resolve_icon_path(item.icon_path)
        if not resolved_path:
            return

        cache_key = (resolved_path, icon_size)

        if resolved_path.lower().endswith(".svg"):
            if cache_key not in self._icon_cache:
                pixmap = QPixmap(icon_size, icon_size)
                pixmap.fill(Qt.GlobalColor.transparent)
                renderer = QSvgRenderer(resolved_path)
                if renderer.isValid():
                    svg_painter = QPainter(pixmap)
                    svg_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    svg_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                    renderer.render(svg_painter)
                    svg_painter.end()
                    self._icon_cache[cache_key] = pixmap
                else:
                    self._icon_cache[cache_key] = QPixmap()
        else:
            if cache_key not in self._icon_cache:
                pixmap = QIcon(resolved_path).pixmap(int(icon_size), int(icon_size))
                self._icon_cache[cache_key] = pixmap

        pixmap = self._icon_cache[cache_key]
        if not pixmap.isNull():
            painter.drawPixmap(int(cx - icon_size / 2), int(cy - icon_size / 2 - 6), pixmap)

    def _draw_item_label(
        self,
        painter: QPainter,
        item: PieSlice,
        index: int,
        total: int,
        mid_angle: float,
        rad_inner: float,
        rad_outer: float,
    ) -> None:
        """Draw the text label for a pie slice (always rendered on top of icons)."""
        rad_mid = (rad_inner + rad_outer) / 2
        rad_angle = math.radians(mid_angle)
        cx = self.center_pos.x() + rad_mid * math.cos(rad_angle)
        cy = self.center_pos.y() + rad_mid * math.sin(rad_angle)

        # Setup Font
        if self._item_font:
            painter.setFont(self._item_font)
        else:
            font = QFont(self.settings.font_family)
            font.setBold(True)
            font.setPointSize(self.text_size)
            painter.setFont(font)

        label = item.label or ""
        if not label:
            return

        icon_size = self.icon_size
        if item.icon_path:
            text_rect = QRectF(cx - 60, cy + icon_size / 2 - 4, 120, 40)
            flags = (
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
            )
        else:
            text_rect = QRectF(cx - 60, cy - 20, 120, 40)
            flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap

        # Determine Text Color
        if self.settings.dynamic_text_color:
            bg_lightness = QColor(item.color).lightness()
            text_color = Qt.GlobalColor.black if bg_lightness > 180 else Qt.GlobalColor.white
            outline_color = (
                QColor(255, 255, 255, 150) if bg_lightness > 180 else QColor(0, 0, 0, 150)
            )
        else:
            text_color = Qt.GlobalColor.white
            outline_color = QColor(0, 0, 0, 150)

        # Draw text outline
        if self.settings.enable_text_outline:
            painter.setPen(outline_color)
            for dx, dy in [
                (-1, -1),
                (0, -1),
                (1, -1),
                (-1, 0),
                (1, 0),
                (-1, 1),
                (0, 1),
                (1, 1),
                (0, 2),
                (2, 0),
                (-2, 0),
                (0, -2),
            ]:
                painter.drawText(text_rect.translated(dx, dy), flags, label)

        # Draw main text body
        painter.setPen(QColor(text_color))
        painter.drawText(text_rect, flags, label)

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
