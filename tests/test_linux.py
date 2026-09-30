"""Tests for wallmotion.platform.linux - Qt-free, headless-safe."""

import json
import os

from wallmotion.platform import linux as L


class TestDetectSession:
    def test_x11(self):
        info = L.detect_session({"XDG_SESSION_TYPE": "x11",
                                 "XDG_CURRENT_DESKTOP": "XFCE"})
        assert info["session"] == "x11"
        assert info["desktops"] == ["xfce"]
        assert not info["is_gnome"]

    def test_wayland_kde(self):
        info = L.detect_session({"XDG_SESSION_TYPE": "wayland",
                                 "XDG_CURRENT_DESKTOP": "KDE"})
        assert info["session"] == "wayland"
        assert info["is_kde"]

    def test_gnome_colon_list(self):
        info = L.detect_session({"XDG_SESSION_TYPE": "wayland",
                                 "XDG_CURRENT_DESKTOP": "ubuntu:GNOME"})
        assert info["is_gnome"]

    def test_wayland_fallback_via_display(self):
        info = L.detect_session({"WAYLAND_DISPLAY": "wayland-0"})
        assert info["session"] == "wayland"

    def test_empty_env(self):
        info = L.detect_session({})
        assert info["session"] == "unknown"
        assert info["desktops"] == []

    def test_case_insensitive(self):
        info = L.detect_session({"XDG_SESSION_TYPE": "X11"})
        assert info["session"] == "x11"


class TestCandidateBackends:
    def test_x11(self):
        assert L.candidate_backends({"session": "x11"}) == ["x11"]

    def test_kde_wayland(self):
        info = {"session": "wayland", "is_kde": True,
                "is_wlroots": False, "is_gnome": False}
        assert L.candidate_backends(info) == ["kde"]

    def test_wlroots(self):
        info = {"session": "wayland", "is_kde": False,
                "is_wlroots": True, "is_gnome": False}
        assert L.candidate_backends(info) == ["wlroots"]

    def test_gnome(self):
        info = {"session": "wayland", "is_kde": False,
                "is_wlroots": False, "is_gnome": True}
        assert L.candidate_backends(info) == ["gnome"]

    def test_tty_has_no_backend(self):
        assert L.candidate_backends({"session": "tty"}) == []


class TestCommands:
    def test_feh(self):
        assert L.feh_command("/a/b.png") == ["feh", "--bg-fill", "/a/b.png"]

    def test_swww(self):
        assert L.swww_command("/a/b.png") == [
            "swww", "img", "--resize", "crop", "/a/b.png"]

    def test_gsettings_sets_both_keys(self):
        cmds = L.gsettings_commands("/a/b.png")
        assert len(cmds) == 2
        assert cmds[0][:3] == ["gsettings", "set",
                               "org.gnome.desktop.background"]
        assert cmds[0][3] == "picture-uri"
        assert cmds[1][3] == "picture-uri-dark"
        assert cmds[0][4].startswith("file://")
        assert cmds[0][4] == cmds[1][4]

    def test_plasma(self):
        assert L.plasma_command("/a/b.png") == [
            "plasma-apply-wallpaperimage", "/a/b.png"]

    def test_mpv_options_muted(self):
        assert L.mpv_options(True, 0.8) == "loop-file=inf no-audio"

    def test_mpv_options_volume(self):
        assert L.mpv_options(False, 0.6) == "loop-file=inf volume=60 mute=no"

    def test_mpv_options_clamped(self):
        assert "volume=100" in L.mpv_options(False, 5.0)
        assert "volume=0" in L.mpv_options(False, -1.0)

    def test_mpvpaper_all_outputs(self):
        cmd = L.mpvpaper_command("/v.mp4", True, 0.3)
        assert cmd[0] == "mpvpaper" and "*" in cmd and "/v.mp4" in cmd

    def test_mpvpaper_named_output_and_ipc(self):
        cmd = L.mpvpaper_command("/v.mp4", False, 0.5,
                                 output="DP-1", ipc_socket="/tmp/x.sock")
        assert "DP-1" in cmd
        assert any("input-ipc-server=/tmp/x.sock" in a for a in cmd)

    def test_xwinwrap_fullscreen_wid_placeholder(self):
        cmd = L.xwinwrap_command("/v.mp4", True, 0.3)
        assert cmd[:4] == ["xwinwrap", "-fs", "-ov", "-fdt"]
        assert "--" in cmd
        assert "WID" in cmd
        assert cmd[cmd.index("--") + 1] == "mpv"


class TestIpc:
    def test_message_format(self):
        msg = L.mpv_ipc_message("volume", 60)
        assert json.loads(msg) == {"command": ["set_property", "volume", 60]}
        assert msg.endswith(b"\n")

    def test_set_to_nowhere_fails_quietly(self):
        assert L.mpv_ipc_set("/nonexistent/wallmotion-test.sock",
                             "volume", 10) is False


class TestBattery:
    def _make_psu(self, tmp_path, name, type_, status):
        d = tmp_path / name
        d.mkdir()
        (d / "type").write_text(type_, encoding="utf-8")
        (d / "status").write_text(status, encoding="utf-8")

    def test_discharging(self, tmp_path):
        self._make_psu(tmp_path, "BAT0", "Battery\n", "Discharging\n")
        assert L.read_battery_status(str(tmp_path)) is True

    def test_charging_is_not_battery(self, tmp_path):
        self._make_psu(tmp_path, "BAT0", "Battery\n", "Charging\n")
        assert L.read_battery_status(str(tmp_path)) is False

    def test_mains_ignored(self, tmp_path):
        self._make_psu(tmp_path, "AC", "Mains\n", "Charging\n")
        assert L.read_battery_status(str(tmp_path)) is False

    def test_missing_dir(self, tmp_path):
        assert L.read_battery_status(str(tmp_path / "nope")) is False


class TestDetectBackend:
    def _env(self, session, desktop):
        return {"XDG_SESSION_TYPE": session, "XDG_CURRENT_DESKTOP": desktop}

    def test_x11_backend_when_tools_present(self, monkeypatch):
        monkeypatch.setattr(L, "_which", lambda name: f"/usr/bin/{name}")
        backend = L.detect_backend(self._env("x11", "XFCE"))
        assert isinstance(backend, L.X11Backend)

    def test_wlroots_backend(self, monkeypatch):
        monkeypatch.setattr(L, "_which", lambda name: f"/usr/bin/{name}")
        backend = L.detect_backend(self._env("wayland", "Hyprland"))
        assert isinstance(backend, L.WlrootsBackend)

    def test_kde_backend(self, monkeypatch):
        monkeypatch.setattr(L, "_which", lambda name: f"/usr/bin/{name}")
        backend = L.detect_backend(self._env("wayland", "KDE"))
        assert isinstance(backend, L.KdeBackend)

    def test_gnome_backend_video_refused(self, monkeypatch):
        monkeypatch.setattr(L, "_which", lambda name: f"/usr/bin/{name}")
        backend = L.detect_backend(self._env("wayland", "GNOME"))
        assert isinstance(backend, L.GnomeBackend)
        assert backend.set_video("/v.mp4", True, 0.3) is False

    def test_no_tools_no_backend(self, monkeypatch):
        monkeypatch.setattr(L, "_which", lambda name: None)
        assert L.detect_backend(self._env("x11", "XFCE")) is None

    def test_tty_no_backend(self, monkeypatch):
        monkeypatch.setattr(L, "_which", lambda name: f"/usr/bin/{name}")
        assert L.detect_backend({"XDG_SESSION_TYPE": "tty"}) is None


class TestAutostart:
    def test_entry_content(self):
        text = L.autostart_entry("/usr/bin/wallmotion")
        assert "Exec=/usr/bin/wallmotion" in text
        assert text.startswith("[Desktop Entry]")

    def test_write_autostart(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert L.write_autostart("/usr/bin/wallmotion") is True
        content = (tmp_path / "autostart" / "wallmotion.desktop").read_text(
            encoding="utf-8")
        assert "Exec=/usr/bin/wallmotion" in content


class TestMisc:
    def test_file_uri(self):
        uri = L.file_uri("/a/b.png")
        assert uri.startswith("file://")
        assert uri.endswith("b.png")
        assert "a" in uri

    def test_describe_session(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "XFCE")
        assert "x11" in L.describe_session()
        del os.environ["XDG_SESSION_TYPE"]
        del os.environ["XDG_CURRENT_DESKTOP"]
