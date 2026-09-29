"""Platform application paths (config, downloads, log).

Single place that decides where files live:
- Windows: keep legacy locations for backward compatibility
  (config next to home, downloads next to the app/exe, log in %TEMP%).
- Linux/macOS: follow the XDG Base Directory specification
  (~/.config, ~/.local/share, ~/.local/state, respecting env overrides).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def _app_base_dir() -> Path:
    """Directory with the executable (frozen .exe) or with the sources.

    For a frozen onefile .exe, sys._MEIPASS must NOT be used (it is a
    temporary unpack dir) - videos belong next to the .exe itself.
    """
    try:
        if getattr(sys, "frozen", False):
            return Path(os.path.abspath(sys.executable)).parent
    except Exception:
        pass
    # wallmotion/paths.py -> repository root (where main.py lives).
    return Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def app_dirs() -> dict[str, Path]:
    """Return platform paths for config, downloads and log files."""
    if sys.platform == "win32":
        return {
            "config": Path.home() / ".live_wallpaper_config.json",
            "downloads": _app_base_dir() / "downloads",
            "log": Path(tempfile.gettempdir()) / "live_wallpaper_debug.log",
        }
    xdg_cfg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    xdg_data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    xdg_state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return {
        "config": xdg_cfg / "wallmotion" / "config.json",
        "downloads": xdg_data / "wallmotion" / "downloads",
        "log": xdg_state / "wallmotion" / "debug.log",
    }


def config_path() -> Path:
    """Full path of the JSON config file."""
    return app_dirs()["config"]


def downloads_dir() -> Path:
    """Directory for downloaded YouTube videos."""
    return app_dirs()["downloads"]


def log_path() -> Path:
    """Path of the debug log file."""
    return app_dirs()["log"]


def ensure_dirs() -> dict[str, Path]:
    """Create parent directories for all paths, return them."""
    dirs = app_dirs()
    for key in ("config", "downloads", "log"):
        try:
            parent = dirs[key].parent if key != "downloads" else dirs[key]
            parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    return dirs
