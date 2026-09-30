"""Tests for wallmotion.cli - pure argument parsing, no Qt needed."""

import pytest

from wallmotion.cli import args_to_command, has_action, parse_args


class TestParseArgs:
    def test_empty(self):
        args = parse_args([])
        assert args.set is None
        assert args.stop is False
        assert args.volume is None

    def test_set(self):
        assert parse_args(["--set", "a.mp4"]).set == "a.mp4"

    def test_stop(self):
        assert parse_args(["--stop"]).stop is True

    def test_mute_unmute_exclusive(self):
        assert parse_args(["--mute"]).mute is True
        with pytest.raises(SystemExit):
            parse_args(["--mute", "--unmute"])

    def test_volume(self):
        assert parse_args(["--volume", "70"]).volume == 70

    def test_version(self):
        assert parse_args(["--version"]).version is True


class TestArgsToCommand:
    def test_empty(self):
        assert args_to_command(parse_args([])) == {}
        assert has_action(parse_args([])) is False

    def test_set(self):
        cmd = args_to_command(parse_args(["--set", "a.mp4"]))
        assert cmd == {"set": "a.mp4"}
        assert has_action(parse_args(["--set", "a.mp4"])) is True

    def test_stop_mute_volume(self):
        cmd = args_to_command(
            parse_args(["--stop", "--mute", "--volume", "40"]))
        assert cmd == {"stop": True, "muted": True, "volume": 40}

    def test_unmute(self):
        assert args_to_command(parse_args(["--unmute"])) == {"muted": False}

    def test_volume_clamped(self):
        assert args_to_command(parse_args(["--volume", "999"]))["volume"] == 100
        assert args_to_command(parse_args(["--volume", "-5"]))["volume"] == 0
