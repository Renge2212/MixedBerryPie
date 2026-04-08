"""Shared rendering logic for Pie Menu and Preview Widget.

Provides a mixin class to ensure the live preview exactly matches the real overlay.
"""

import math
from typing import Any

from PyQt6.QtCore import QPoint, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from src.core.config import COLOR_PRESETS, AppSettings, PieSlice
from src.core.utils import resolve_icon_path
from src.ui.components.custom_widgets import _render_icon_pixmap

# ── Angle constants for pie layout ────────────────────────────────────────────
MAX_FAN_SPAN_DEG = 180.0  # Maximum angular span for a submenu fan (degrees)
FAN_SPAN_PER_ITEM_DEG = 60.0  # Angular span allocated per submenu child (degrees)
ROOT_START_ANGLE_DEG = -90.0  # Root layer: first item centered at "Up" (degrees)


class PieRenderMixin:
    """Provides methods for rendering a pie menu."""

    settings: AppSettings
    center_pos: QPoint
    radius_inner: float
    radius_outer: float
    ring_thickness: float
    ring_gap: float
    icon_size: int
    text_size: int
    _icon_cache: dict[tuple[str, int], Any]
    _item_font: QFont | None

    def _get_root_items(self) -> list[PieSlice]:
        """Return the root-level menu items for angle calculations.

        Subclasses must override if the root items differ from self.menu_items
        (e.g. PiePreviewWidget uses _parent_items_stack[0]).
        """
        return getattr(self, "menu_items", [])

    def _get_slice_center_angle(self, depth: int, path: list[int]) -> float:
        """Calculate the absolute center angle (degrees, 0=Up) of a slice at depth.

        Works by traversing from root through submenu levels, computing
        each level's fan span and child center angle.
        """
        root_items = self._get_root_items()
        if not root_items or not path or depth < 0 or depth >= len(path):
            return 0.0

        num_root = len(root_items)
        if num_root == 0:
            return 0.0
        root_span = 360.0 / num_root
        center = ROOT_START_ANGLE_DEG + (path[0] * root_span)

        if depth == 0:
            return center

        current_list = getattr(root_items[path[0]], "submenu_items", None) or []
        for d in range(1, depth + 1):
            if not current_list or d >= len(path):
                break
            n = len(current_list)
            fan_span = min(MAX_FAN_SPAN_DEG, FAN_SPAN_PER_ITEM_DEG * n)
            slice_span = fan_span / n
            idx = path[d]
            start = center - fan_span / 2
            center = start + idx * slice_span + slice_span / 2
            if idx < len(current_list):
                current_list = getattr(current_list[idx], "submenu_items", None) or []

        return center % 360

    def _draw_layer(
        self,
        painter: QPainter,
        depth: int,
        items: list[PieSlice],
        path: list[int],
        phase: str = "both",
        alpha_mod: float = 1.0,
    ) -> None:
        """Recursively draw a layer of the pie menu."""
        if not items:
            return

        num_items = len(items)
        # Root is 360, children fan out up to 180 depending on count
        angle_span = (
            360.0 / num_items
            if depth == 0
            else min(MAX_FAN_SPAN_DEG, FAN_SPAN_PER_ITEM_DEG * num_items) / num_items
        )

        # Calculate start angle for this layer
        if depth == 0:
            start_angle_base = ROOT_START_ANGLE_DEG - (angle_span / 2)
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
            base_color.setAlpha(int(255 * opacity_percent / 100 * alpha_mod))

            # 2. Slice Fill
            if phase in ("both", "background"):
                if is_selected:
                    # Selected: Brighter fill
                    fill_color = QColor(effective_color_str).lighter(130)
                    fill_color.setAlpha(int(255 * opacity_percent / 100 * alpha_mod))
                    painter.fillPath(path_obj, QBrush(fill_color))

                    # Glow/Border outline in the item's color
                    glow_color = QColor(effective_color_str)
                    glow_color.setAlpha(int(200 * alpha_mod))
                    glow_pen = QPen(glow_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                    glow_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.strokePath(path_obj, glow_pen)
                else:
                    # Unselected: Original item color
                    painter.fillPath(path_obj, QBrush(base_color))

            # 3. Draw Label and Icon
            if phase in ("both", "content", "icons"):
                self._draw_item_icon(
                    painter,
                    item,
                    i,
                    num_items,
                    start_angle + angle_span / 2,
                    rad_inner,
                    rad_outer,
                    alpha_mod,
                )
            if phase in ("both", "content", "labels"):
                self._draw_item_label(
                    painter,
                    item,
                    i,
                    num_items,
                    start_angle + angle_span / 2,
                    rad_inner,
                    rad_outer,
                    alpha_mod,
                )

        # Recursively draw the next layer if an item is selected and has submenus
        if selected_idx != -1 and selected_idx < num_items:
            selected_item = items[selected_idx]
            if getattr(selected_item, "submenu_items", None):
                self._draw_layer(
                    painter, depth + 1, selected_item.submenu_items, path, phase, alpha_mod
                )

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
        max_reduction = max(max_reduction, 0)

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
        alpha_mod: float = 1.0,
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

        if cache_key not in self._icon_cache:
            rendered = _render_icon_pixmap(resolved_path, icon_size)
            self._icon_cache[cache_key] = rendered if rendered else QPixmap()

        pixmap = self._icon_cache[cache_key]
        if not pixmap.isNull():
            if alpha_mod < 1.0:
                painter.setOpacity(alpha_mod)
                painter.drawPixmap(int(cx - icon_size / 2), int(cy - icon_size / 2 - 6), pixmap)
                painter.setOpacity(1.0)
            else:
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
        alpha_mod: float = 1.0,
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
            text_color = (
                QColor(0, 0, 0, int(255 * alpha_mod))
                if bg_lightness > 180
                else QColor(255, 255, 255, int(255 * alpha_mod))
            )
            outline_color = (
                QColor(255, 255, 255, int(150 * alpha_mod))
                if bg_lightness > 180
                else QColor(0, 0, 0, int(150 * alpha_mod))
            )
        else:
            text_color = QColor(255, 255, 255, int(255 * alpha_mod))
            outline_color = QColor(0, 0, 0, int(150 * alpha_mod))

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
