"""Tests for wallmotion.updatecheck - pure logic, no network in tests."""

from wallmotion.updatecheck import (
    CHECK_INTERVAL_SECONDS,
    is_newer,
    parse_version,
    should_auto_check,
)


class TestParseVersion:
    def test_simple(self):
        assert parse_version("v1.0.4") == (1, 0, 4)

    def test_no_v_prefix(self):
        assert parse_version("2.1") == (2, 1)

    def test_garbage(self):
        assert parse_version("") == ()
        assert parse_version("latest") == ()


class TestIsNewer:
    def test_newer(self):
        assert is_newer("v1.0.4", "v1.0.3") is True
        assert is_newer("v1.0.10", "v1.0.4") is True  # numeric, not lexical

    def test_same_or_older(self):
        assert is_newer("v1.0.4", "v1.0.4") is False
        assert is_newer("v1.0.3", "v1.0.4") is False

    def test_first_run_never_nags(self):
        assert is_newer("v1.0.4", None) is False
        assert is_newer("v1.0.4", "") is False

    def test_empty_latest(self):
        assert is_newer("", "v1.0.3") is False


class TestThrottle:
    def test_never_checked(self):
        assert should_auto_check(0.0, now=1000.0) is True
        assert should_auto_check(None, now=1000.0) is True

    def test_recent_check_skipped(self):
        now = 2000000.0
        assert should_auto_check(now - 1000.0, now=now) is False

    def test_old_check_runs(self):
        now = 2000000.0
        assert should_auto_check(now - CHECK_INTERVAL_SECONDS - 1,
                                 now=now) is True
