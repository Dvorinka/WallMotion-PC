"""Auto-pause rules: pause video wallpaper during fullscreen apps / on battery.

Same idea as Lively: a fullscreen game should get the GPU back, and a
laptop on battery should not waste power on an invisible wallpaper.
Sensors are Windows-only (guarded imports, like wallmotion.win32);
the decision logic is pure and unit-tested.
"""

from __future__ import annotations

import ctypes
import sys

if sys.platform == "win32":
    import win32api
    import win32gui
else:
    win32api = None
    win32gui = None

_MONITOR_DEFAULTTONEAREST = 2

# Shell windows that are never a "fullscreen app" (desktop itself).
_SHELL_CLASSES = {"Progman", "WorkerW", "SHELLDLL_DefView"}

# Poll interval (ms) and clean polls required before resuming, so that
# alt-tabbing does not flap pause/play every second.
POLL_INTERVAL_MS = 2000
RESUME_AFTER_CLEAN_POLLS = 2


class _SystemPowerStatus(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_byte),  # 0=battery, 1=AC, 255=unknown
        ("BatteryFlag", ctypes.c_byte),
        ("BatteryLifePercent", ctypes.c_byte),
        ("Reserved1", ctypes.c_byte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


def is_fullscreen_rect(window_rect: tuple, monitor_rect: tuple) -> bool:
    """Pure check: does the window cover its whole monitor?"""
    try:
        return tuple(window_rect) == tuple(monitor_rect)
    except Exception:
        return False


def should_pause(
    fullscreen_active: bool,
    on_battery: bool,
    *,
    pause_on_fullscreen: bool,
    pause_on_battery: bool,
) -> bool:
    """Pure decision: pause when any enabled rule fires."""
    try:
        if pause_on_fullscreen and fullscreen_active:
            return True
        if pause_on_battery and on_battery:
            return True
    except Exception:
        pass
    return False


def parse_ac_line_status(ac_line_status: int) -> bool:
    """True when the AC status byte means 'running on battery'."""
    try:
        return int(ac_line_status) == 0
    except Exception:
        return False


def foreground_window_info() -> tuple | None:
    """(hwnd, rect) of the foreground window, or None. Windows-only."""
    if win32gui is None:
        return None
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        try:
            cls = win32gui.GetClassName(hwnd)
            if cls in _SHELL_CLASSES:
                return None
        except Exception:
            pass
        rect = win32gui.GetWindowRect(hwnd)
        return (hwnd, rect)
    except Exception:
        return None


def monitor_rect_for_window(hwnd) -> tuple | None:
    """Monitor rect (left, top, right, bottom) nearest to hwnd, or None."""
    if win32api is None or win32gui is None:
        return None
    try:
        monitor = win32api.MonitorFromWindow(hwnd, _MONITOR_DEFAULTTONEAREST)
        info = win32api.GetMonitorInfo(monitor)
        return tuple(info["Monitor"])
    except Exception:
        return None


def is_fullscreen_app_active() -> bool:
    """True when the foreground window covers its whole monitor."""
    try:
        info = foreground_window_info()
        if not info:
            return False
        hwnd, rect = info
        monitor_rect = monitor_rect_for_window(hwnd)
        if not monitor_rect:
            return False
        return is_fullscreen_rect(rect, monitor_rect)
    except Exception:
        return False


def is_on_battery() -> bool:
    """True when running on battery power. False on desktops / unknown."""
    if sys.platform != "win32":
        return False
    try:
        status = _SystemPowerStatus()
        ok = ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
        if not ok:
            return False
        return parse_ac_line_status(status.ACLineStatus)
    except Exception:
        return False
