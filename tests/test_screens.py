"""Tests for wallmotion.screens - pure geometry + monitor enumeration."""

from wallmotion.screens import (
    duplicate_targets,
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


class TestDuplicateTargets:
    MONS = [
        {"index": 0, "x": 0, "y": 0, "w": 1920, "h": 1080, "primary": False},
        {"index": 1, "x": 1920, "y": 0, "w": 1920, "h": 1080, "primary": True},
    ]

    def test_single_monitor_span(self):
        assert duplicate_targets("all", []) == [None]
        one = [dict(self.MONS[0])]
        assert duplicate_targets("all", one) == [None]

    def test_multi_monitor_primary_first(self):
        targets = duplicate_targets("all", self.MONS)
        assert [t["index"] for t in targets] == [1, 0]

    def test_specific_monitor(self):
        targets = duplicate_targets(0, self.MONS)
        assert targets == [dict(self.MONS[0])]

    def test_unknown_index_falls_back(self):
        assert duplicate_targets(99, self.MONS) == [None]


class TestPhysicalMonitors:
    def test_returns_list_of_dicts(self):
        mons = get_physical_monitors()
        assert isinstance(mons, list)
        for m in mons:
            assert {"index", "x", "y", "w", "h", "primary"} <= set(m)
            assert m["w"] > 0 and m["h"] > 0
