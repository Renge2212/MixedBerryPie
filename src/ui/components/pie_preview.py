import math

from PyQt6.QtCore import QPoint, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import QWidget

from src.core.config import PieSlice


class PiePreviewWidget(QWidget):
    """A small widget that shows a live preview of the pie menu."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.menu_items: list[PieSlice] = []
        self.opacity_percent = 80
        self.color_mode = "individual"
        self.unified_color = "#448AFF"
        self.selected_preset = "Mixed Berry"
        self.current_palette: list[str] = []
        self.setMinimumSize(220, 220)
        self.radius_inner = 25
        self.radius_outer = 85

    def update_opacity(self, opacity: int) -> None:
        self.opacity_percent = opacity
        self.update()

    def update_items(self, items: list[PieSlice]) -> None:
        self.menu_items = items
        self.update()

    def update_unified_color(
        self, mode: str, color: str, preset: str, palette: list[str] | None = None
    ) -> None:
        self.color_mode = mode
        self.unified_color = color
        self.selected_preset = preset
        self.current_palette = palette or []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        center_pos = QPoint(self.width() // 2, self.height() // 2)

        num_items = len(self.menu_items)
        if num_items == 0:
            # Draw empty state placeholder
            painter.setPen(QPen(QColor(128, 128, 128, 100), 1, Qt.PenStyle.DashLine))
            painter.drawEllipse(center_pos, self.radius_outer, self.radius_outer)
            painter.setPen(QColor(128, 128, 128, 150))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.tr("No Items"))
            return

        slice_span = 360 / num_items

        # Draw central glow
        glow = QRadialGradient(center_pos.x(), center_pos.y(), self.radius_outer + 10)
        glow.setColorAt(0, QColor(0, 0, 0, 30))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center_pos, self.radius_outer + 10, self.radius_outer + 10)

        for i, item in enumerate(self.menu_items):
            angle_start = (90 + slice_span / 2) - (i * slice_span)

            effective_color_str = item.color
            if self.color_mode == "unified":
                effective_color_str = self.unified_color
            elif self.color_mode == "preset":
                palette = self.current_palette
                if palette:
                    color_idx = i % len(palette)
                    # Adjacency fix for circular menus
                    if num_items > 1 and i == num_items - 1 and color_idx == 0 and len(palette) > 1:
                        color_idx = (color_idx + 1) % len(palette)
                    effective_color_str = palette[color_idx]
                else:
                    effective_color_str = "#CCCCCC"

            color = QColor(effective_color_str)
            color.setAlpha(int(255 * self.opacity_percent / 100))

            rect_outer = QRectF(
                center_pos.x() - self.radius_outer,
                center_pos.y() - self.radius_outer,
                self.radius_outer * 2,
                self.radius_outer * 2,
            )

            rect_inner = QRectF(
                center_pos.x() - self.radius_inner,
                center_pos.y() - self.radius_inner,
                self.radius_inner * 2,
                self.radius_inner * 2,
            )

            sweep = -slice_span

            path = QPainterPath()
            path.arcMoveTo(rect_outer, angle_start)
            path.arcTo(rect_outer, angle_start, sweep)
            path.arcTo(rect_inner, angle_start + sweep, -sweep)
            path.closeSubpath()

            painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
            painter.setBrush(QBrush(color))
            painter.drawPath(path)

            # Draw micro label
            font = QFont("Segoe UI", 8, QFont.Weight.Bold)
            painter.setFont(font)

            mid_angle_deg = angle_start + sweep / 2
            mid_angle_rad = math.radians(mid_angle_deg)

            text_radius = (self.radius_inner + self.radius_outer) / 2
            tx = center_pos.x() + text_radius * math.cos(mid_angle_rad)
            ty = center_pos.y() - text_radius * math.sin(mid_angle_rad)

            fm = painter.fontMetrics()
            label = item.label[:6] + ".." if len(item.label) > 8 else item.label
            tw = fm.horizontalAdvance(label)

            painter.setPen(QColor(255, 255, 255))
            painter.drawText(int(tx - tw / 2), int(ty + fm.height() / 4), label)
