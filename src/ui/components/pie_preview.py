from typing import Any

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QRadialGradient
from PyQt6.QtWidgets import QWidget

from src.core.config import AppSettings, PieSlice
from src.ui.components.pie_renderer import PieRenderMixin


class PiePreviewWidget(QWidget, PieRenderMixin):
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

        # Text/Font settings
        self.font_family = "Segoe UI"
        self.text_size = 9
        self.enable_text_outline = True
        self.dynamic_text_color = False

        # Icon settings
        self.icon_size = 64

        # Whether to show dummy items when empty
        self.preview_mode = False

        # Mock Settings for mixin
        self.settings = AppSettings()
        self.settings.menu_opacity = self.opacity_percent
        self.settings.color_mode = self.color_mode
        self.settings.unified_color = self.unified_color
        self.settings.selected_preset = self.selected_preset
        self.settings.font_family = self.font_family
        self.settings.text_size = self.text_size
        self.settings.icon_size = self.icon_size
        self.settings.enable_text_outline = self.enable_text_outline
        self.settings.dynamic_text_color = self.dynamic_text_color

        self.setMinimumSize(350, 350)

        # Legacy fixed radii (used only when depth==0 and preview is tiny)
        self.radius_inner: float = 25.0
        self.radius_outer: float = 85.0
        self.ring_thickness: float = 40.0
        self.ring_gap: float = 15.0

        # Submenu context - set by update_context()
        self._depth: int = 0
        # Stack of items at each level: [root_items, depth1_items, ...]
        self._parent_items_stack: list[list[PieSlice]] = []
        # Index of the selected item at each level (needed to know fan center)
        self._selected_indices: list[int] = []

        # Mixin requirements
        self.center_pos = QPoint(0, 0)
        self._icon_cache: dict[tuple[str, int], Any] = {}
        self._item_font: QFont | None = None
        self.active_path: list[int] = []

    def _sync_settings(self) -> None:
        """Sync local properties to the mock settings object for the mixin."""
        self.settings.menu_opacity = self.opacity_percent
        self.settings.color_mode = self.color_mode
        self.settings.unified_color = self.unified_color
        self.settings.selected_preset = self.selected_preset
        self.settings.font_family = self.font_family
        self.settings.text_size = self.text_size
        self.settings.icon_size = self.icon_size
        self.settings.enable_text_outline = self.enable_text_outline
        self.settings.dynamic_text_color = self.dynamic_text_color

        self._item_font = QFont(self.settings.font_family)
        self._item_font.setBold(True)
        self._item_font.setPointSize(self.text_size)

    # ── Public API ─────────────────────────────────────────────────────────

    def update_opacity(self, opacity: int) -> None:
        self.opacity_percent = opacity
        self._sync_settings()
        self.update()

    def update_font_settings(
        self, family: str, size: int, outline: bool, dynamic_color: bool
    ) -> None:
        """Update font, size, outline, and dynamic color settings for the preview."""
        self.font_family = family
        self.text_size = size
        self.enable_text_outline = outline
        self.dynamic_text_color = dynamic_color
        self._sync_settings()
        self.update()

    def update_icon_settings(self, size: int) -> None:
        """Update the icon size for the preview."""
        self.icon_size = size
        self._icon_cache.clear()
        self._sync_settings()
        self.update()

    def update_items(self, items: list[PieSlice]) -> None:
        """Backward-compatible helper (depth 0)."""
        self.menu_items = items
        self._depth = 0
        self._parent_items_stack = []
        self._selected_indices = []
        self.active_path = []
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
        self.active_path = selected_indices or []
        self.update()

    def update_unified_color(
        self, mode: str, color: str, preset: str, palette: list[str] | None = None
    ) -> None:
        self.color_mode = mode
        self.unified_color = color
        self.selected_preset = preset
        self.current_palette = palette or []
        self._sync_settings()
        self.update()

    # ── Internal helpers ───────────────────────────────────────────────────

    def _compute_radii(self, cx: int, total_rings: int) -> tuple[float, float, float, float]:
        """Compute (r_hole, ring_thickness, ring_gap, max_r) that fit inside the widget."""
        max_r = cx - 4
        inner_frac = 0.25  # same as overlay: radius_inner = radius_outer * 0.25
        r_hole = max_r * inner_frac
        usable = max_r - r_hole
        gap_frac = 0.05
        # The mixin expects absolute values for these
        gap = usable * gap_frac
        thickness = (usable - gap * max(0, total_rings - 1)) / max(1, total_rings)

        self.radius_inner = r_hole
        self.radius_outer = r_hole + thickness
        self.ring_thickness = thickness
        self.ring_gap = gap

        return r_hole, thickness, gap, max_r

    def _get_slice_center_angle(
        self,
        depth: int,  # which level's center angle to compute (0 = root)
        path: list[int],
    ) -> float:
        """Compute the center angle (degrees, 0=Up / Qt convention reversed) of the
        selected slice at a given depth, mirroring overlay._get_slice_center_angle."""
        if not self._parent_items_stack or depth >= len(path):
            return 0.0

        # Root layer: 360° / n, first item centered at -90° (Up)
        root_items = self._parent_items_stack[0]
        n_root = len(root_items)
        if n_root == 0:
            return 0.0
        root_span = 360.0 / n_root
        center = -90.0 + path[0] * root_span

        if depth == 0:
            return center

        # Traverse submenu levels
        current_list = (
            root_items[path[0]].submenu_items if len(path) > 0 and len(root_items) > path[0] else []
        )
        for d in range(1, depth + 1):
            if not current_list or d >= len(path):
                break
            n = len(current_list)
            fan_span = min(180.0, 60.0 * n)
            slice_span = fan_span / n
            idx = path[d]
            start = center - fan_span / 2
            child_center = start + idx * slice_span + slice_span / 2
            center = child_center
            if d < len(path) and idx < len(current_list):
                current_list = getattr(current_list[idx], "submenu_items", []) or []

        return center % 360

    # ── paintEvent ─────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        self.center_pos = QPoint(cx, cy)
        self._sync_settings()

        items_to_draw = self.menu_items

        # Generate dummy items if empty (for previewing colors/fonts/icons)
        if len(items_to_draw) == 0 and self.preview_mode:
            dummy_count = (
                len(self.current_palette)
                if self.color_mode == "preset" and self.current_palette
                else 6
            )
            dummy_count = max(3, dummy_count)  # At least 3 slices to look like a pie

            # List of sample icons to use for the dummy items
            sample_icons = [
                "icons/home.svg",
                "icons/settings.svg",
                "icons/search.svg",
                "icons/folder.svg",
                "icons/help.svg",
                "icons/plus.svg",
            ]

            items_to_draw = []
            for i in range(dummy_count):
                icon_path = sample_icons[i % len(sample_icons)]
                items_to_draw.append(
                    PieSlice(
                        label=self.tr("Sample {0}").format(i + 1),
                        key="",
                        color="#448AFF",
                        icon_path=icon_path,
                    )
                )

        # How many rings are visible: parent rings + current submenu ring
        total_rings = self._depth + 1
        _, _, _, max_r = self._compute_radii(min(cx, cy), total_rings)

        # Draw glow
        glow = QRadialGradient(cx, cy, max_r + 6)
        glow.setColorAt(0, QColor(0, 0, 0, 20))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(cx, cy), int(max_r + 6), int(max_r + 6))

        if self._depth == 0:
            # Root: full 360° ring
            self._draw_layer(
                painter, 0, items_to_draw, self.active_path, phase="background", alpha_mod=1.0
            )
            self._draw_layer(
                painter, 0, items_to_draw, self.active_path, phase="icons", alpha_mod=1.0
            )
            self._draw_layer(
                painter, 0, items_to_draw, self.active_path, phase="labels", alpha_mod=1.0
            )
        else:
            # Draw each parent ring (dimmed), then the current submenu ring (full brightness)
            for d, parent_items in enumerate(self._parent_items_stack):
                self._draw_layer(
                    painter,
                    d,
                    parent_items,
                    self.active_path[:d],
                    phase="background",
                    alpha_mod=0.35,
                )
                self._draw_layer(
                    painter, d, parent_items, self.active_path[:d], phase="icons", alpha_mod=0.35
                )
                self._draw_layer(
                    painter, d, parent_items, self.active_path[:d], phase="labels", alpha_mod=0.35
                )

            # Current (outermost) submenu ring
            d_sub = len(self._parent_items_stack)
            self._draw_layer(
                painter, d_sub, items_to_draw, self.active_path, phase="background", alpha_mod=1.0
            )
            self._draw_layer(
                painter, d_sub, items_to_draw, self.active_path, phase="icons", alpha_mod=1.0
            )
            self._draw_layer(
                painter, d_sub, items_to_draw, self.active_path, phase="labels", alpha_mod=1.0
            )
