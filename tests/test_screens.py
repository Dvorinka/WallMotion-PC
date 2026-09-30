"""Tests for wallmotion.screens - pure geometry + monitor enumeration."""

from wallmotion.screens import get_physical_monitors, place_canvas


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


class TestPhysicalMonitors:
    def test_returns_list_of_dicts(self):
        mons = get_physical_monitors()
        assert isinstance(mons, list)
        for m in mons:
            assert {"index", "x", "y", "w", "h", "primary"} <= set(m)
            assert m["w"] > 0 and m["h"] > 0
