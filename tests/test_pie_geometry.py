"""Tests for pie menu geometry: angle calculation, polar math, layer detection, fan logic."""

import math

import pytest
from PyQt6.QtCore import QPoint

from src.core.config import AppSettings, PieSlice
from src.ui.components.pie_renderer import (
    PieRenderMixin,
)
from src.ui.overlay import PieOverlay

# qapp fixture is provided by conftest.py


# ── Stub for testing PieRenderMixin without Qt widgets ──────────────────────


class _GeometryStub(PieRenderMixin):
    """Minimal stub to test PieRenderMixin pure methods."""

    def __init__(self, items: list[PieSlice]) -> None:
        self.menu_items = items
        self.settings = AppSettings()
        self.center_pos = QPoint(0, 0)
        self.radius_inner = 50
        self.radius_outer = 200
        self.ring_thickness = 100
        self.ring_gap = 15
        self.icon_size = 64
        self.text_size = 9
        self._icon_cache = {}
        self._item_font = None


def _make_items(n: int) -> list[PieSlice]:
    return [PieSlice(label=f"Item{i}", key=str(i), color="#FF0000") for i in range(n)]


# ── _get_slice_center_angle ────────────────────────────────────────────────


class TestGetSliceCenterAngle:
    def test_root_4items_idx0(self):
        stub = _GeometryStub(_make_items(4))
        # 4 items: span = 90°, idx 0 center = -90 + 0*90 = -90
        # depth==0 returns raw center (no mod 360)
        angle = stub._get_slice_center_angle(0, [0])
        assert angle == pytest.approx(-90.0, abs=0.01)

    def test_root_4items_idx1(self):
        stub = _GeometryStub(_make_items(4))
        angle = stub._get_slice_center_angle(0, [1])
        assert angle == pytest.approx(0.0, abs=0.01)

    def test_root_4items_idx2(self):
        stub = _GeometryStub(_make_items(4))
        angle = stub._get_slice_center_angle(0, [2])
        assert angle == pytest.approx(90.0, abs=0.01)

    def test_root_4items_idx3(self):
        stub = _GeometryStub(_make_items(4))
        angle = stub._get_slice_center_angle(0, [3])
        assert angle == pytest.approx(180.0, abs=0.01)

    def test_root_6items_idx0(self):
        stub = _GeometryStub(_make_items(6))
        # 6 items: span = 60°, idx 0 center = -90
        angle = stub._get_slice_center_angle(0, [0])
        assert angle == pytest.approx(-90.0, abs=0.01)

    def test_empty_path_returns_zero(self):
        stub = _GeometryStub(_make_items(4))
        assert stub._get_slice_center_angle(0, []) == 0.0

    def test_depth1_submenu(self):
        """Submenu child angle is relative to parent's center."""
        parent = PieSlice(label="P", key="p", color="#FF0000")
        child0 = PieSlice(label="C0", key="c0", color="#00FF00")
        child1 = PieSlice(label="C1", key="c1", color="#0000FF")
        parent.submenu_items = [child0, child1]
        stub = _GeometryStub([parent, *_make_items(3)])

        # Parent center = -90 (270°). 2 children, fan_span=min(180, 60*2)=120°
        # child0: start = -90 - 60 = -150, center = -150 + 30 = -120 → 240
        angle = stub._get_slice_center_angle(1, [0, 0])
        assert angle == pytest.approx(240.0, abs=0.01)

        # child1: center = -150 + 60 + 30 = -60 → 300
        angle = stub._get_slice_center_angle(1, [0, 1])
        assert angle == pytest.approx(300.0, abs=0.01)


# ── _calc_polar ────────────────────────────────────────────────────────────


@pytest.fixture
def overlay(qapp):
    items = _make_items(4)
    settings = AppSettings()
    settings.show_animations = False
    ov = PieOverlay(items, settings)
    ov.center_pos = QPoint(250, 250)
    ov.is_visible = True
    yield ov
    ov.close()
    ov.deleteLater()


class TestCalcPolar:
    def test_directly_above(self, overlay):
        dist, deg = overlay._calc_polar(QPoint(250, 150))
        assert dist == pytest.approx(100.0, abs=0.1)
        assert deg == pytest.approx(0.0, abs=0.5)

    def test_directly_right(self, overlay):
        dist, deg = overlay._calc_polar(QPoint(350, 250))
        assert dist == pytest.approx(100.0, abs=0.1)
        assert deg == pytest.approx(90.0, abs=0.5)

    def test_directly_below(self, overlay):
        dist, deg = overlay._calc_polar(QPoint(250, 350))
        assert dist == pytest.approx(100.0, abs=0.1)
        assert deg == pytest.approx(180.0, abs=0.5)

    def test_directly_left(self, overlay):
        dist, deg = overlay._calc_polar(QPoint(150, 250))
        assert dist == pytest.approx(100.0, abs=0.1)
        assert deg == pytest.approx(270.0, abs=0.5)

    def test_diagonal_ne(self, overlay):
        # 45° clockwise from up = NE
        offset = int(70.71)  # ~100 * cos(45°)
        dist, deg = overlay._calc_polar(QPoint(250 + offset, 250 - offset))
        assert dist == pytest.approx(math.sqrt(offset**2 + offset**2), abs=1.0)
        assert deg == pytest.approx(45.0, abs=1.0)


# ── _determine_target_layer ───────────────────────────────────────────────


class TestDetermineTargetLayer:
    def test_inside_root(self, overlay):
        assert overlay._determine_target_layer(150.0) == 0

    def test_at_boundary(self, overlay):
        assert overlay._determine_target_layer(float(overlay.radius_outer)) == 0

    def test_first_submenu(self, overlay):
        # Just past radius_outer
        dist = overlay.radius_outer + 10
        assert overlay._determine_target_layer(float(dist)) == 1

    def test_second_submenu(self, overlay):
        # Past radius_outer + ring_thickness + ring_gap
        dist = overlay.radius_outer + overlay.ring_thickness + overlay.ring_gap + 10
        assert overlay._determine_target_layer(float(dist)) == 2


# ── _is_within_fan ─────────────────────────────────────────────────────────


class TestIsWithinFan:
    # center_angle is in raw coords (0=right), adj_degrees is adjusted (0=up).
    # Conversion: adj = (raw + 90) % 360.
    # s_adj = (center_angle - fan_span/2 + 90) % 360

    def test_center_hit(self, overlay):
        # center_angle=0 (raw right) → adj center=90. Fan 60° → adj 60..120
        within, _ = overlay._is_within_fan(90.0, 0.0, 60.0)
        assert within is True

    def test_edge_hit_start(self, overlay):
        # Fan adj 60..120, check adj=60 (start edge)
        within, r = overlay._is_within_fan(60.0, 0.0, 60.0)
        assert within is True
        assert r == pytest.approx(0.0, abs=1.0)

    def test_miss(self, overlay):
        # adj=30 is outside fan adj 60..120
        within, _ = overlay._is_within_fan(30.0, 0.0, 60.0)
        assert within is False

    def test_wraparound(self, overlay):
        # center_angle=-90 (raw up) → adj center=0. Fan 40° → adj 340..20 (wraps)
        within, _ = overlay._is_within_fan(5.0, -90.0, 40.0)
        assert within is True

    def test_exact_end(self, overlay):
        # Fan adj 60..120, check adj=120 (end edge)
        within, r = overlay._is_within_fan(120.0, 0.0, 60.0)
        assert within is True
        assert r == pytest.approx(60.0, abs=1.0)

    def test_full_360(self, overlay):
        """Full 360° fan: any angle is within."""
        within, _ = overlay._is_within_fan(180.0, 0.0, 360.0)
        assert within is True


# ── _should_lock_to_submenu ───────────────────────────────────────────────


class TestShouldLockToSubmenu:
    def test_invalid_index(self, overlay):
        assert overlay._should_lock_to_submenu(-1, overlay.menu_items, 90.0, 0, []) is False

    def test_no_submenu(self, overlay):
        assert overlay._should_lock_to_submenu(0, overlay.menu_items, 90.0, 0, []) is False

    def test_within_fan(self, qapp):
        """Cursor within submenu fan → True."""
        parent = PieSlice(label="P", key="p", color="#FF0000")
        child = PieSlice(label="C", key="c", color="#00FF00")
        parent.submenu_items = [child]
        items = [parent, *_make_items(3)]

        settings = AppSettings()
        settings.show_animations = False
        ov = PieOverlay(items, settings)
        ov.is_visible = True
        ov.center_pos = QPoint(250, 250)

        # Parent idx=0 center angle ≈ 270° (-90°). Fan with 1 child → span=180°
        # That means fan covers roughly 180..360 (adj_degrees with +90 offset)
        # adj_degrees 0 (up) corresponds to pointing at parent center
        result = ov._should_lock_to_submenu(0, items, 0.0, 0, [])
        assert result is True

        ov.close()
        ov.deleteLater()

    def test_outside_fan(self, qapp):
        """Cursor outside submenu fan → False."""
        parent = PieSlice(label="P", key="p", color="#FF0000")
        child = PieSlice(label="C", key="c", color="#00FF00")
        parent.submenu_items = [child]
        items = [parent, *_make_items(3)]

        settings = AppSettings()
        settings.show_animations = False
        ov = PieOverlay(items, settings)
        ov.is_visible = True
        ov.center_pos = QPoint(250, 250)

        # 180° (opposite direction) should be outside the fan
        result = ov._should_lock_to_submenu(0, items, 180.0, 0, [])
        assert result is False

        ov.close()
        ov.deleteLater()
