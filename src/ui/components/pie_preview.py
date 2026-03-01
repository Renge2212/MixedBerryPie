import math

from PyQt6.QtCore import QPoint, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import QWidget

from src.core.config import PieSlice


class PiePreviewWidget(QWidget):
    """A small widget that shows a live preview of the pie menu.

    Matches the actual overlay rendering: depth-0 is a full 360° ring,
    depth-1+ is a fan arc (≤180°) centered on the parent slice's midpoint.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.menu_items: list[PieSlice] = []
        self.opacity_percent = 80
        self.color_mode = "individual"
        self.unified_color = "#448AFF"
        self.selected_preset = "Mixed Berry"
        self.current_palette: list[str] = []
        self.setMinimumSize(220, 220)

        # Legacy fixed radii (used only when depth==0 and preview is tiny)
        self.radius_inner = 25
        self.radius_outer = 85

        # Submenu context - set by update_context()
        self._depth: int = 0
        # Stack of items at each level: [root_items, depth1_items, ...]
        self._parent_items_stack: list[list[PieSlice]] = []
        # Index of the selected item at each level (needed to know fan center)
        self._selected_indices: list[int] = []

    # ── Public API ─────────────────────────────────────────────────────────

    def update_opacity(self, opacity: int) -> None:
        self.opacity_percent = opacity
        self.update()

    def update_items(self, items: list[PieSlice]) -> None:
        """Backward-compatible helper (depth 0)."""
        self.menu_items = items
        self._depth = 0
        self._parent_items_stack = []
        self._selected_indices = []
        self.update()

    def update_context(
        self,
        items: list[PieSlice],
        depth: int = 0,
        parent_items_stack: list[list[PieSlice]] | None = None,
        selected_indices: list[int] | None = None,
    ) -> None:
        """Update the preview with full navigation context.

        Args:
            items: Items at the current editing level.
            depth: How many levels deep we are.
            parent_items_stack: Items at each ancestor level [root, depth1, ...].
            selected_indices: Selected item index at each ancestor level,
                              used to compute the fan center angle.
        """
        self.menu_items = items
        self._depth = depth
        self._parent_items_stack = parent_items_stack or []
        self._selected_indices = selected_indices or []
        self.update()

    def update_unified_color(
        self, mode: str, color: str, preset: str, palette: list[str] | None = None
    ) -> None:
        self.color_mode = mode
        self.unified_color = color
        self.selected_preset = preset
        self.current_palette = palette or []
        self.update()

    # ── Internal helpers ───────────────────────────────────────────────────

    def _get_item_color(self, item: PieSlice, index: int, total: int) -> str:
        if self.color_mode == "unified":
            return self.unified_color
        if self.color_mode == "preset":
            palette = self.current_palette
            if palette:
                color_idx = index % len(palette)
                if total > 1 and index == total - 1 and color_idx == 0 and len(palette) > 1:
                    color_idx = (color_idx + 1) % len(palette)
                return palette[color_idx]
            return "#CCCCCC"
        return item.color

    def _compute_radii(self, cx: int, total_rings: int) -> tuple[float, float, float, float]:
        """Compute (r_hole, ring_thickness, ring_gap, max_r) that fit inside the widget."""
        max_r = cx - 4
        inner_frac = 0.25  # same as overlay: radius_inner = radius_outer * 0.25
        r_hole = max_r * inner_frac
        usable = max_r - r_hole
        gap_frac = 0.05
        gap = usable * gap_frac
        thickness = (usable - gap * max(0, total_rings - 1)) / max(1, total_rings)
        return r_hole, thickness, gap, max_r

    def _get_parent_center_angle(
        self,
        depth: int,  # which level's center angle to compute (0 = root)
    ) -> float:
        """Compute the center angle (degrees, 0=Up / Qt convention reversed) of the
        selected slice at a given depth, mirroring overlay._get_slice_center_angle."""
        if not self._parent_items_stack or depth >= len(self._selected_indices):
            return 0.0

        # Root layer: 360° / n, first item centered at -90° (Up)
        root_items = self._parent_items_stack[0]
        n_root = len(root_items)
        if n_root == 0:
            return 0.0
        root_span = 360.0 / n_root
        center = -90.0 + self._selected_indices[0] * root_span

        if depth == 0:
            return center

        # Traverse submenu levels
        current_list = (
            root_items[self._selected_indices[0]].submenu_items if self._selected_indices else []
        )
        for d in range(1, depth + 1):
            if not current_list or d >= len(self._selected_indices):
                break
            n = len(current_list)
            fan_span = min(180.0, 60.0 * n)
            slice_span = fan_span / n
            idx = self._selected_indices[d]
            start = center - fan_span / 2
            child_center = start + idx * slice_span + slice_span / 2
            center = child_center
            if d < len(self._selected_indices) and idx < len(current_list):
                current_list = getattr(current_list[idx], "submenu_items", []) or []

        return center % 360

    def _draw_ring(
        self,
        painter: QPainter,
        cx: int,
        cy: int,
        items: list[PieSlice],
        r_inner: float,
        r_outer: float,
        start_angle_base: float,
        angle_span: float,
        alpha_mod: float = 1.0,
    ) -> None:
        """Draw one ring / fan of pie slices.

        Angles follow the same convention as the overlay (math degrees, 0=right, CCW+,
        but internally negated for Qt's CW system).
        """
        n = len(items)
        if n == 0:
            return

        for i, item in enumerate(items):
            start = start_angle_base + i * angle_span

            color_str = self._get_item_color(item, i, n)
            color = QColor(color_str)
            alpha = int(255 * self.opacity_percent / 100 * alpha_mod)
            color.setAlpha(alpha)

            # Build the donut slice path (same approach as overlay._create_slice_path)
            qt_start = -start  # overlay negates to convert to Qt CW
            qt_span = -angle_span

            rect_outer = QRectF(cx - r_outer, cy - r_outer, r_outer * 2, r_outer * 2)
            rect_inner = QRectF(cx - r_inner, cy - r_inner, r_inner * 2, r_inner * 2)

            path = QPainterPath()
            path.arcMoveTo(rect_outer, qt_start)
            path.arcTo(rect_outer, qt_start, qt_span)
            qt_inner_end = qt_start + qt_span
            path.arcTo(rect_inner, qt_inner_end, -qt_span)
            path.closeSubpath()

            painter.setPen(QPen(QColor(255, 255, 255, int(50 * alpha_mod)), 0.5))
            painter.setBrush(QBrush(color))
            painter.drawPath(path)

            # Label
            font = QFont("Segoe UI", 7, QFont.Weight.Bold)
            painter.setFont(font)
            mid_angle_deg = start + angle_span / 2
            mid_rad = math.radians(mid_angle_deg)
            text_r = (r_inner + r_outer) / 2
            tx = cx + text_r * math.cos(mid_rad)
            ty = cy + text_r * math.sin(mid_rad)
            fm = painter.fontMetrics()
            label = item.label[:6] + ".." if len(item.label) > 8 else item.label
            tw = fm.horizontalAdvance(label)
            label_color = QColor(255, 255, 255, int(220 * alpha_mod))
            painter.setPen(label_color)
            painter.drawText(int(tx - tw / 2), int(ty + fm.height() / 4), label)

    # ── paintEvent ─────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2

        num_items = len(self.menu_items)
        if num_items == 0:
            painter.setPen(QPen(QColor(128, 128, 128, 100), 1, Qt.PenStyle.DashLine))
            r = min(cx, cy) - 4
            painter.drawEllipse(QPoint(cx, cy), r, r)
            painter.setPen(QColor(128, 128, 128, 150))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.tr("No Items"))
            return

        # How many rings are visible: parent rings + current submenu ring
        total_rings = self._depth + 1
        r_hole, thickness, gap, max_r = self._compute_radii(min(cx, cy), total_rings)

        # Draw glow
        glow = QRadialGradient(cx, cy, max_r + 6)
        glow.setColorAt(0, QColor(0, 0, 0, 20))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(cx, cy), int(max_r + 6), int(max_r + 6))

        if self._depth == 0:
            # Root: full 360° ring
            n = len(self.menu_items)
            span = 360.0 / n
            start = -90.0 - span / 2  # first item centered at Up (-90°)
            self._draw_ring(painter, cx, cy, self.menu_items, r_hole, max_r, start, span)
        else:
            # Draw each parent ring (dimmed), then the current submenu ring (full brightness)
            for d, parent_items in enumerate(self._parent_items_stack):
                r_in = r_hole + d * (thickness + gap)
                r_out = r_in + thickness

                if d == 0:
                    # Root layer: 360°
                    n = len(parent_items)
                    span = 360.0 / max(1, n)
                    start = -90.0 - span / 2
                else:
                    # Submenu fan
                    n = len(parent_items)
                    fan_span = min(180.0, 60.0 * n)
                    span = fan_span / max(1, n)
                    parent_center = self._get_parent_center_angle(d - 1)
                    start = parent_center - fan_span / 2

                self._draw_ring(
                    painter, cx, cy, parent_items, r_in, r_out, start, span, alpha_mod=0.35
                )

            # Current (outermost) submenu ring
            d_sub = len(self._parent_items_stack)
            r_in_sub = r_hole + d_sub * (thickness + gap)
            r_out_sub = r_in_sub + thickness

            n_sub = len(self.menu_items)
            fan_span_sub = min(180.0, 60.0 * n_sub)
            span_sub = fan_span_sub / max(1, n_sub)
            parent_center_sub = self._get_parent_center_angle(d_sub - 1)
            start_sub = parent_center_sub - fan_span_sub / 2

            self._draw_ring(
                painter,
                cx,
                cy,
                self.menu_items,
                r_in_sub,
                r_out_sub,
                start_sub,
                span_sub,
                alpha_mod=1.0,
            )
