"""Linux backends: static image + video via external renderers.

Design (see docs/STACK_ANALYSIS.md appendix): instead of re-implementing
rendering, orchestrate proven tools - feh/swww/gsettings/
/// plasma-apply-wallpaperimage for images, mpvpaper or xwinwrap+mpv
for video. Session capability comes from $XDG_SESSION_TYPE /
$XDG_CURRENT_DESKTOP.

This module is Qt-free (stdlib only) so it stays unit-testable headless.
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

# Wayland compositors we drive with mpvpaper/swww.
WLROOTS_DESKTOPS = frozenset({
    "sway", "hyprland", "wlroots", "wayfire", "river", "dwl",
    "labwc", "niri",
})

MPV_IPC_SOCKET_NAME = "wallmotion-mpv.sock"


def detect_session(env=None) -> dict:
    """Describe the graphical session. Pure function, unit-tested.

    Returns {session, desktops, is_gnome, is_kde, is_wlroots} where
    session is "x11" | "wayland" | "tty" | "unknown".
    """
    env = env if env is not None else os.environ
    try:
        session = str(env.get("XDG_SESSION_TYPE", "") or "").lower()
    except Exception:
        session = ""
    if not session and env.get("WAYLAND_DISPLAY"):
        session = "wayland"
    try:
        raw = str(env.get("XDG_CURRENT_DESKTOP", "") or "").lower()
    except Exception:
        raw = ""
    desktops = [d for d in raw.replace(";", ":").split(":") if d]
    return {
        "session": session or "unknown",
        "desktops": desktops,
        "is_gnome": "gnome" in desktops,
        "is_kde": "kde" in desktops or "plasma" in desktops,
        "is_wlroots": bool(set(desktops) & set(WLROOTS_DESKTOPS)),
    }


def candidate_backends(info: dict) -> list:
    """Backend names in priority order for the detected session."""
    session = info.get("session", "unknown")
    if session == "x11":
        return ["x11"]
    if session == "wayland":
        if info.get("is_kde"):
            return ["kde"]
        if info.get("is_wlroots"):
            return ["wlroots"]
        if info.get("is_gnome"):
            return ["gnome"]
        return ["wlroots", "kde", "gnome"]
    if session == "tty":
        return []
    return ["x11", "wlroots", "kde", "gnome"]


def _which(name: str) -> str | None:
    try:
        return shutil.which(name)
    except Exception:
        return None


def file_uri(path: str) -> str:
    """Absolute file:// URI for gsettings."""
    try:
        return "file://" + os.path.abspath(path)
    except Exception:
        return "file://" + path


def run_command(cmd: list, timeout: int = 15) -> tuple:
    """Run a command, never raise. Returns (ok, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        return (proc.returncode == 0, proc.stdout or "", proc.stderr or "")
    except Exception as e:
        return (False, "", repr(e))


# --- command builders (pure, unit-tested) -------------------------------

def feh_command(path: str) -> list:
    return ["feh", "--bg-fill", path]


def swww_command(path: str) -> list:
    return ["swww", "img", "--resize", "crop", path]


def gsettings_commands(path: str) -> list:
    uri = file_uri(path)
    base = ["gsettings", "set", "org.gnome.desktop.background"]
    return [base + ["picture-uri", uri], base + ["picture-uri-dark", uri]]


def plasma_command(path: str) -> list:
    return ["plasma-apply-wallpaperimage", path]


def mpv_options(muted: bool, volume: float) -> str:
    """mpv options forwarded by mpvpaper -o (and used for plain mpv)."""
    try:
        vol = max(0, min(100, int(round(float(volume) * 100))))
    except Exception:
        vol = 30
    if muted:
        return "loop-file=inf no-audio"
    return f"loop-file=inf volume={vol} mute=no"


def ipc_socket_path() -> str:
    """Where the mpv JSON IPC socket lives."""
    base = os.environ.get("XDG_RUNTIME_DIR", "") or tempfile.gettempdir()
    return os.path.join(base, MPV_IPC_SOCKET_NAME)


def mpvpaper_command(path: str, muted: bool, volume: float,
                     output: str = "*", ipc_socket: str | None = None) -> list:
    """mpvpaper on all outputs (*) or one named output (e.g. DP-1)."""
    opts = mpv_options(muted, volume)
    if ipc_socket:
        opts += f" input-ipc-server={ipc_socket}"
    return ["mpvpaper", "-o", opts, output, path]


def xwinwrap_geometry(monitor: dict | None) -> str | None:
    """'WxH+X+Y' for one monitor, or None for fullscreen. Pure."""
    try:
        if not monitor:
            return None
        w, h = max(1, int(monitor["w"])), max(1, int(monitor["h"]))
        x, y = int(monitor["x"]), int(monitor["y"])
        return f"{w}x{h}+{x}+{y}"
    except Exception:
        return None


def xwinwrap_command(path: str, muted: bool, volume: float,
                     ipc_socket: str | None = None,
                     geometry: str | None = None) -> list:
    """xwinwrap fullscreen (-fs) or on one monitor (-g WxH+X+Y), plus mpv
    (WID is substituted by xwinwrap)."""
    mpv_cmd = ["mpv", "-wid", "WID", "--loop-file=inf", "--no-osc",
               "--no-input-default-bindings"]
    if muted:
        mpv_cmd.append("--mute=yes")
    else:
        try:
            vol = max(0, min(100, int(round(float(volume) * 100))))
        except Exception:
            vol = 30
        mpv_cmd.append(f"--volume={vol}")
    if ipc_socket:
        mpv_cmd.append(f"--input-ipc-server={ipc_socket}")
    mpv_cmd.append(path)
    if geometry:
        return ["xwinwrap", "-g", geometry, "-ov", "-fdt", "--"] + mpv_cmd
    return ["xwinwrap", "-fs", "-ov", "-fdt", "--"] + mpv_cmd


def mpv_ipc_message(prop: str, value) -> bytes:
    """One JSON IPC line for mpv (set_property)."""
    import json
    return (json.dumps({"command": ["set_property", prop, value]}) + "\n").encode()


def mpv_ipc_set(sock_path: str, prop: str, value, timeout: float = 2.0) -> bool:
    """Live set of an mpv property via JSON IPC. Never raises."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.settimeout(timeout)
            sock.connect(sock_path)
            sock.sendall(mpv_ipc_message(prop, value))
            return True
        finally:
            try:
                sock.close()
            except Exception:
                pass
    except Exception:
        return False


def ensure_swww_daemon() -> bool:
    """Make sure swww-daemon runs (needed before swww img)."""
    ok, _out, _err = run_command(["swww", "query"], timeout=5)
    if ok:
        return True
    try:
        subprocess.Popen(["swww-daemon"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except Exception:
        return False
    for _ in range(10):
        time.sleep(0.2)
        ok, _out, _err = run_command(["swww", "query"], timeout=5)
        if ok:
            return True
    return False


def read_battery_status(sysfs_root: str = "/sys/class/power_supply") -> bool:
    """True when a battery supply reports Discharging. Never raises."""
    try:
        entries = os.listdir(sysfs_root)
    except Exception:
        return False
    for name in entries:
        type_path = os.path.join(sysfs_root, name, "type")
        status_path = os.path.join(sysfs_root, name, "status")
        try:
            with open(type_path, encoding="utf-8") as f:
                if f.read().strip().lower() != "battery":
                    continue
            with open(status_path, encoding="utf-8") as f:
                if f.read().strip().lower() == "discharging":
                    return True
        except Exception:
            continue
    return False


def autostart_entry(exec_path: str) -> str:
    """Content of the ~/.config/autostart/wallmotion.desktop file."""
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=WallMotion\n"
        f"Exec={exec_path}\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def write_autostart(exec_path: str) -> bool:
    """Write the autostart entry. Returns success."""
    try:
        directory = os.path.join(
            os.environ.get("XDG_CONFIG_HOME",
                           os.path.join(os.path.expanduser("~"), ".config")),
            "autostart",
        )
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, "wallmotion.desktop"),
                  "w", encoding="utf-8") as f:
            f.write(autostart_entry(exec_path))
        return True
    except Exception:
        return False


# --- backends ------------------------------------------------------------

class LinuxProcessBackend:
    """Base: owns one child process group; stop() kills it all."""

    name = "linux-base"
    required_tools: tuple = ()

    def __init__(self):
        self._proc = None

    def missing_tools(self) -> list:
        return [t for t in self.required_tools if not _which(t)]

    def available(self) -> bool:
        return not self.missing_tools()

    def _spawn(self, cmd: list) -> bool:
        self.stop()
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception:
            self._proc = None
            return False

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
        except Exception:
            try:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass

    def set_paused(self, paused: bool) -> None:
        """Pause/resume playback via mpv IPC (autopause rules)."""
        mpv_ipc_set(ipc_socket_path(), "pause", bool(paused))


class X11Backend(LinuxProcessBackend):
    """X11: feh for images, fullscreen xwinwrap+mpv for video."""

    name = "x11"
    required_tools = ("feh", "xwinwrap", "mpv")

    def set_image(self, path: str) -> bool:
        if not _which("feh"):
            return False
        ok, _out, _err = run_command(feh_command(path))
        return ok

    def set_video(self, path: str, muted: bool, volume: float,
                  geometry: str | None = None) -> bool:
        if not (_which("xwinwrap") and _which("mpv")):
            return False
        return self._spawn(xwinwrap_command(path, muted, volume,
                                           ipc_socket=ipc_socket_path(),
                                           geometry=geometry))

    def set_muted(self, muted: bool) -> None:
        mpv_ipc_set(ipc_socket_path(), "mute", bool(muted))

    def set_volume(self, volume: float) -> None:
        try:
            vol = max(0, min(100, int(round(float(volume) * 100))))
        except Exception:
            return
        mpv_ipc_set(ipc_socket_path(), "volume", vol)


class WlrootsBackend(LinuxProcessBackend):
    """wlroots Wayland (sway/hyprland/...): swww for images, mpvpaper video."""

    name = "wlroots"
    required_tools = ("swww", "mpvpaper")

    def set_image(self, path: str) -> bool:
        if not _which("swww"):
            return False
        if not ensure_swww_daemon():
            return False
        ok, _out, _err = run_command(swww_command(path))
        return ok

    def set_video(self, path: str, muted: bool, volume: float,
                  geometry: str | None = None) -> bool:
        # mpvpaper always covers all outputs (*) in v1; per-output names
        # need wlr enumeration on real hardware (see TODO). Geometry is
        # accepted for API parity and ignored.
        if not _which("mpvpaper"):
            return False
        return self._spawn(mpvpaper_command(path, muted, volume,
                                           ipc_socket=ipc_socket_path()))

    def set_muted(self, muted: bool) -> None:
        mpv_ipc_set(ipc_socket_path(), "mute", bool(muted))

    def set_volume(self, volume: float) -> None:
        try:
            vol = max(0, min(100, int(round(float(volume) * 100))))
        except Exception:
            return
        mpv_ipc_set(ipc_socket_path(), "volume", vol)


class KdeBackend(WlrootsBackend):
    """KDE Plasma: own image tool, mpvpaper video (works on KWin Wayland)."""

    name = "kde"
    required_tools = ("plasma-apply-wallpaperimage", "mpvpaper")

    def set_image(self, path: str) -> bool:
        if not _which("plasma-apply-wallpaperimage"):
            return False
        ok, _out, _err = run_command(plasma_command(path))
        return ok


class GnomeBackend(LinuxProcessBackend):
    """GNOME: gsettings for images. Video unsupported in v1 (needs the
    Hanabi Shell extension - there is no public video-background API)."""

    name = "gnome"
    required_tools = ("gsettings",)

    HANABI_NOTE = ("GNOME Wayland has no video-wallpaper API. "
                   "Install the Hanabi extension (github.com/jeffshee/gnome-ext-hanabi).")

    def set_image(self, path: str) -> bool:
        if not _which("gsettings"):
            return False
        for cmd in gsettings_commands(path):
            ok, _out, _err = run_command(cmd)
            if not ok:
                return False
        return True

    def set_video(self, path: str, muted: bool, volume: float,
                  geometry: str | None = None) -> bool:
        return False

    def set_paused(self, paused: bool) -> None:
        pass

    def set_muted(self, muted: bool) -> None:
        pass

    def set_volume(self, volume: float) -> None:
        pass


_BACKENDS = {
    "x11": X11Backend,
    "wlroots": WlrootsBackend,
    "kde": KdeBackend,
    "gnome": GnomeBackend,
}


def detect_backend(env=None):
    """First available backend for this session, or None.

    GNOME returns its backend even for video-less operation (image works,
    set_video reports False with the Hanabi note).
    """
    info = detect_session(env)
    for name in candidate_backends(info):
        cls = _BACKENDS.get(name)
        if cls is None:
            continue
        backend = cls()
        try:
            if backend.available():
                return backend
        except Exception:
            continue
    # Last resort: a backend whose image tool exists (partial support).
    for name in candidate_backends(info):
        cls = _BACKENDS.get(name)
        if cls is None:
            continue
        backend = cls()
        try:
            if not backend.missing_tools() or len(backend.missing_tools()) < len(
                backend.required_tools
            ):
                return backend
        except Exception:
            continue
    return None


def describe_session() -> str:
    """One-line session description for logs and status messages."""
    info = detect_session()
    desks = ",".join(info["desktops"]) or "?"
    return f"session={info['session']} desktop={desks}"


def is_on_battery_linux() -> bool:
    """Battery sensor for the autopause rules (sysfs, no dependencies)."""
    if not sys.platform.startswith("linux"):
        return False
    return read_battery_status()
