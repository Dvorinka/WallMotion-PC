"""Tests for wallmotion.screens - pure geometry + monitor enumeration."""

from wallmotion.screens import (
    get_physical_monitors,
    place_canvas,
    qt_monitors_to_physical,
)


class TestPlaceCanvas:
    def test_none_covers_whole_parent(self):
        assert place_canvas((0, 0, 1920, 1080), None) == (0, 0, 1920, 1080)

    def test_primary_monitor(self):
        mon = {"x": 0, "y": 0, "w": 1920, "h": 1080}
        assert place_canvas((0, 0, 1920, 1080), mon) == (0, 0, 1920, 1080)

    def test_secondary_monitor_offset(self):
        parent = (0, 0, 3840, 1080)
        mon = {"x": 1920, "y": 0, "w": 1920, "h": 1080}
        assert place_canvas(parent, mon) == (1920, 0, 1920, 1080)

    def test_negative_offset_monitor(self):
        parent = (-1920, 0, 1920, 1080)
        mon = {"x": -1920, "y": 0, "w": 1920, "h": 1080}
        assert place_canvas(parent, mon) == (0, 0, 1920, 1080)

    def test_invalid_monitor_falls_back_to_parent(self):
        assert place_canvas((0, 0, 800, 600), {}) == (0, 0, 800, 600)
        assert place_canvas((0, 0, 800, 600), None) == (0, 0, 800, 600)


class TestQtMonitorsToPhysical:
    def test_maps_qt_data(self):
        info = {"screens": [
            {"index": 0, "x": 0, "y": 0, "width": 1920, "height": 1080,
             "physical_width": 1920, "physical_height": 1080,
             "primary": True, "dpr": 1.0},
            {"index": 1, "x": 1920, "y": 0, "width": 1280, "height": 720,
             "physical_width": 2560, "physical_height": 1440,
             "primary": False, "dpr": 2.0},
        ]}
        mons = qt_monitors_to_physical(info)
        assert mons == [
            {"index": 0, "x": 0, "y": 0, "w": 1920, "h": 1080, "primary": True},
            {"index": 1, "x": 1920, "y": 0, "w": 2560, "h": 1440,
             "primary": False},
        ]

    def test_empty(self):
        assert qt_monitors_to_physical({}) == []
        assert qt_monitors_to_physical({"screens": []}) == []


class TestPhysicalMonitors:
    def test_returns_list_of_dicts(self):
        mons = get_physical_monitors()
        assert isinstance(mons, list)
        for m in mons:
            assert {"index", "x", "y", "w", "h", "primary"} <= set(m)
            assert m["w"] > 0 and m["h"] > 0
