"""Tests for wallmotion.volumememory - pure dict helpers, no Qt needed."""

from wallmotion.volumememory import lookup, remember


class TestLookup:
    def test_hit(self):
        store = {"/a.mp4": {"volume": 70, "muted": False}}
        assert lookup(store, "/a.mp4") == {"volume": 70, "muted": False}

    def test_miss(self):
        assert lookup({}, "/a.mp4") is None
        assert lookup(None, "/a.mp4") is None
        assert lookup({"/a.mp4": {"volume": 1, "muted": True}}, "/b.mp4") is None

    def test_clamped(self):
        store = {"/a.mp4": {"volume": 999, "muted": 1}}
        assert lookup(store, "/a.mp4") == {"volume": 100, "muted": True}

    def test_broken_entry(self):
        assert lookup({"/a.mp4": "junk"}, "/a.mp4") is None
        assert lookup({"/a.mp4": {"volume": "x"}}, "/a.mp4") is None


class TestRemember:
    def test_store_and_recall(self):
        store = remember({}, "/a.mp4", 40, True)
        assert lookup(store, "/a.mp4") == {"volume": 40, "muted": True}

    def test_overwrite(self):
        store = remember({"/a.mp4": {"volume": 10, "muted": True}},
                         "/a.mp4", 80, False)
        assert lookup(store, "/a.mp4") == {"volume": 80, "muted": False}

    def test_trims_oldest(self):
        store = {}
        for i in range(5):
            store = remember(store, f"/v{i}.mp4", 10, True, limit=3)
        assert len(store) == 3
        assert lookup(store, "/v0.mp4") is None
        assert lookup(store, "/v1.mp4") is None
        assert lookup(store, "/v4.mp4") is not None

    def test_touch_moves_to_recent(self):
        store = {"/a.mp4": {"volume": 1, "muted": True},
                 "/b.mp4": {"volume": 2, "muted": True}}
        store = remember(store, "/a.mp4", 50, False, limit=2)
        # /b.mp4 is now oldest
        store = remember(store, "/c.mp4", 60, False, limit=2)
        assert lookup(store, "/b.mp4") is None
        assert lookup(store, "/a.mp4") is not None

    def test_empty_path_ignored(self):
        assert remember({}, "", 10, True) == {}
