"""Tests for wallmotion.paths - Windows compat + XDG on Linux."""

import os
import sys

from wallmotion import paths


class TestAppDirs:
    def test_windows_keeps_legacy_locations(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        dirs = paths.app_dirs()
        assert dirs["config"].name == ".live_wallpaper_config.json"
        assert dirs["downloads"].name == "downloads"
        assert dirs["log"].name == "live_wallpaper_debug.log"

    def test_linux_uses_xdg_defaults(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "linux")
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: fake_home))
        for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
            monkeypatch.delenv(var, raising=False)
        dirs = paths.app_dirs()
        assert dirs["config"] == fake_home / ".config" / "wallmotion" / "config.json"
        assert (
            dirs["downloads"]
            == fake_home / ".local/share" / "wallmotion" / "downloads"
        )
        assert dirs["log"] == fake_home / ".local/state" / "wallmotion" / "debug.log"

    def test_linux_respects_xdg_env_overrides(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "linux")
        cfg = tmp_path / "cfg"
        data = tmp_path / "data"
        state = tmp_path / "state"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
        monkeypatch.setenv("XDG_DATA_HOME", str(data))
        monkeypatch.setenv("XDG_STATE_HOME", str(state))
        dirs = paths.app_dirs()
        assert dirs["config"] == cfg / "wallmotion" / "config.json"
        assert dirs["downloads"] == data / "wallmotion" / "downloads"
        assert dirs["log"] == state / "wallmotion" / "debug.log"

    def test_ensure_dirs_creates_parents(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "linux")
        cfg = tmp_path / "cfg"
        data = tmp_path / "data"
        state = tmp_path / "state"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
        monkeypatch.setenv("XDG_DATA_HOME", str(data))
        monkeypatch.setenv("XDG_STATE_HOME", str(state))
        dirs = paths.ensure_dirs()
        assert dirs["config"].parent.is_dir()
        assert dirs["downloads"].is_dir()
        assert dirs["log"].parent.is_dir()

    def test_module_constants_match_helpers(self):
        from wallmotion.config import CONFIG_PATH
        from wallmotion.utils import DEBUG_LOG
        from wallmotion.youtube import YT_DIR

        assert os.path.basename(CONFIG_PATH) in (
            ".live_wallpaper_config.json",
            "config.json",
        )
        assert os.path.basename(YT_DIR) == "downloads"
        assert os.path.basename(DEBUG_LOG) in (
            "live_wallpaper_debug.log",
            "debug.log",
        )
