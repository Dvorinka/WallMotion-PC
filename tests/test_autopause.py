"""Tests for wallmotion.autopause - pure decision logic, no Win32 needed."""

from wallmotion.autopause import (
    is_fullscreen_rect,
    parse_ac_line_status,
    should_pause,
)


class TestShouldPause:
    def test_nothing_fires(self):
        assert not should_pause(
            False, False, pause_on_fullscreen=True, pause_on_battery=True
        )

    def test_fullscreen_rule(self):
        assert should_pause(
            True, False, pause_on_fullscreen=True, pause_on_battery=False
        )
        assert not should_pause(
            True, False, pause_on_fullscreen=False, pause_on_battery=False
        )

    def test_battery_rule(self):
        assert should_pause(
            False, True, pause_on_fullscreen=False, pause_on_battery=True
        )
        assert not should_pause(
            False, True, pause_on_fullscreen=False, pause_on_battery=False
        )

    def test_either_rule_fires(self):
        assert should_pause(
            True, True, pause_on_fullscreen=True, pause_on_battery=True
        )
        # Only fullscreen enabled, only battery active -> no pause.
        assert not should_pause(
            False, True, pause_on_fullscreen=True, pause_on_battery=False
        )


class TestFullscreenRect:
    def test_exact_match(self):
        assert is_fullscreen_rect((0, 0, 1920, 1080), (0, 0, 1920, 1080))

    def test_windowed(self):
        assert not is_fullscreen_rect((100, 100, 1800, 900), (0, 0, 1920, 1080))

    def test_borderless_offset_by_one(self):
        assert not is_fullscreen_rect((0, 0, 1920, 1079), (0, 0, 1920, 1080))

    def test_secondary_monitor(self):
        assert is_fullscreen_rect(
            (1920, 0, 3840, 1080), (1920, 0, 3840, 1080)
        )


class TestAcLineStatus:
    def test_battery(self):
        assert parse_ac_line_status(0) is True

    def test_ac_power(self):
        assert parse_ac_line_status(1) is False

    def test_unknown_means_no_pause(self):
        assert parse_ac_line_status(255) is False
