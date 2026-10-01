"""Screen measurement (Qt + WinAPI fallback)."""

from __future__ import annotations

import sys

from wallmotion.win32 import win32api


def _qapplication():
    """QApplication, imported lazily.

    Keeps this module importable without Qt (headless CI): only the
    functions that actually query screens need it. Pure helpers
    (place_canvas) and the WinAPI path work anywhere.
    """
    from PySide6.QtWidgets import QApplication
    return QApplication


def get_physical_monitors() -> list:
    """Physical monitors via WinAPI (EnumDisplayMonitors).

    Return [{index, x, y, w, h, primary}] in physical pixels
    (virtual desktop coordinates). Empty list on non-Windows.
    Order = enumeration order; primary always has primary=True.
    """
    monitors = []
    if sys.platform != "win32" or win32api is None:
        return monitors
    try:
        found = []
        # pywin32: EnumDisplayMonitors() returns [(hmon, hdc, rect)].
        for hmonitor, _hdc, _rect in win32api.EnumDisplayMonitors():
            try:
                info = win32api.GetMonitorInfo(hmonitor)
                mon = info.get("Monitor", (0, 0, 0, 0))
                flags = info.get("Flags", 0)
                found.append((mon, bool(flags & 1)))  # MONITORINFOF_PRIMARY = 1
            except Exception:
                continue
        for i, ((left, top, right, bottom), primary) in enumerate(found):
            monitors.append({
                "index": i,
                "x": int(left), "y": int(top),
                "w": max(1, int(right - left)), "h": max(1, int(bottom - top)),
                "primary": primary,
            })
    except Exception:
        pass
    return monitors


def qt_monitors_to_physical(screen_info: dict) -> list:
    """Build [{index, x, y, w, h, primary}] from Qt measure_screens() data.

    Sizes are physical pixels; offsets reuse Qt logical coordinates, which
    match physical pixels at 100% scaling (the common X11 case). Used on
    Linux where EnumDisplayMonitors does not exist. Pure, unit-tested.
    """
    monitors = []
    try:
        for i, s in enumerate(screen_info.get("screens", [])):
            monitors.append({
                "index": i,
                "x": int(s.get("x", 0)),
                "y": int(s.get("y", 0)),
                "w": max(1, int(s.get("physical_width", 0))),
                "h": max(1, int(s.get("physical_height", 0))),
                "primary": bool(s.get("primary", i == 0)),
            })
    except Exception:
        pass
    return monitors


def place_canvas(parent_rect: tuple, monitor: dict | None) -> tuple:
    """Compute (x, y, w, h) canvas relative to the parent window. Pure function for tests.

    parent_rect: (x1, y1, x2, y2) of the parent in screen coordinates.
    monitor: {x, y, w, h} in screen coordinates, or None = whole parent.
    """
    px1, py1, px2, py2 = parent_rect
    if not monitor:
        return (0, 0, max(1, px2 - px1), max(1, py2 - py1))
    try:
        mx, my = int(monitor["x"]), int(monitor["y"])
        mw, mh = max(1, int(monitor["w"])), max(1, int(monitor["h"]))
    except Exception:
        return (0, 0, max(1, px2 - px1), max(1, py2 - py1))
    return (mx - px1, my - py1, mw, mh)


def get_virtual_screen_rect():
    """Return (x, y, w, h) spanning all monitors. Fallback to primary."""
    try:
        QApplication = _qapplication()
        screens = QApplication.screens()
        if screens:
            left = min(s.geometry().left() for s in screens)
            top = min(s.geometry().top() for s in screens)
            right = max(s.geometry().right() + 1 for s in screens)
            bottom = max(s.geometry().bottom() + 1 for s in screens)
            return left, top, right - left, bottom - top
    except Exception:
        pass
    # Fallback via WinAPI
    try:
        x = win32api.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        y = win32api.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        w = win32api.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        h = win32api.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
        return x, y, w, h
    except Exception:
        pass
    try:
        geo = _qapplication().primaryScreen().geometry()
        return geo.x(), geo.y(), geo.width(), geo.height()
    except Exception:
        return (0, 0, 0, 0)


def measure_screens() -> dict:
    """Measure all connected screens.

    Return dict:
      screens: [{index, x, y, width, height (logical),
                 physical_width, physical_height (actual pixels),
                 primary, dpr}]
      virtual: (x, y, w, h) spanning all monitors (logical coordinates)
      primary: (w, h) physical pixels of the primary screen
    """
    info = {"screens": [], "virtual": (0, 0, 0, 0), "primary": (0, 0)}
    try:
        QApplication = _qapplication()
        app = QApplication.instance()
        screens = app.screens() if app is not None else []
        for i, s in enumerate(screens):
            g = s.geometry()
            try:
                dpr = float(s.devicePixelRatio() or 1.0)
            except Exception:
                dpr = 1.0
            is_primary = False
            try:
                is_primary = (s == app.primaryScreen())
            except Exception:
                pass
            info["screens"].append({
                "index": i,
                "x": g.x(), "y": g.y(),
                "width": g.width(), "height": g.height(),
                "physical_width": int(round(g.width() * dpr)),
                "physical_height": int(round(g.height() * dpr)),
                "primary": is_primary,
                "dpr": dpr,
            })
        if info["screens"]:
            prim = next((x for x in info["screens"] if x["primary"]), info["screens"][0])
            info["primary"] = (prim["physical_width"], prim["physical_height"])
            left = min(x["x"] for x in info["screens"])
            top = min(x["y"] for x in info["screens"])
            right = max(x["x"] + x["width"] for x in info["screens"])
            bottom = max(x["y"] + x["height"] for x in info["screens"])
            info["virtual"] = (left, top, right - left, bottom - top)
            return info
    except Exception:
        pass
    # Fallback via WinAPI (returns physical pixels)
    try:
        x = win32api.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        y = win32api.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        w = win32api.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        h = win32api.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
        pw = win32api.GetSystemMetrics(0)  # SM_CXSCREEN
        ph = win32api.GetSystemMetrics(1)  # SM_CYSCREEN
        info["virtual"] = (x, y, w, h)
        info["primary"] = (pw, ph)
        info["screens"] = [{
            "index": 0, "x": x, "y": y, "width": w, "height": h,
            "physical_width": pw, "physical_height": ph,
            "primary": True, "dpr": 1.0,
        }]
    except Exception:
        pass
    return info
