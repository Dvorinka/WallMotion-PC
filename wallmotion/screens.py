"""Mereni obrazovek (Qt + WinAPI fallback)."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from wallmotion.win32 import win32api


def get_physical_monitors() -> list:
    """Fyzicke monitory pres WinAPI (EnumDisplayMonitors).

    Vrati [{index, x, y, w, h, primary}] ve fyzickych pixelech
    (souradnice virtualni plochy). Na ne-Windows prazdny seznam.
    Poradi = poradi enumerace; primary má vzdy primary=True.
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


def place_canvas(parent_rect: tuple, monitor: dict | None) -> tuple:
    """Spocita (x, y, w, h) platna vuci parent oknu. Cista funkce pro testy.

    parent_rect: (x1, y1, x2, y2) rodice v screen souradnicich.
    monitor: {x, y, w, h} ve screen souradnicich, nebo None = cely parent.
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
    """Vrati (x, y, w, h) pres vsechny monitory. Fallback na primarni."""
    try:
        screens = QApplication.screens()
        if screens:
            left = min(s.geometry().left() for s in screens)
            top = min(s.geometry().top() for s in screens)
            right = max(s.geometry().right() + 1 for s in screens)
            bottom = max(s.geometry().bottom() + 1 for s in screens)
            return left, top, right - left, bottom - top
    except Exception:
        pass
    # Fallback pres WinAPI
    try:
        x = win32api.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        y = win32api.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        w = win32api.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        h = win32api.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
        return x, y, w, h
    except Exception:
        pass
    geo = QApplication.primaryScreen().geometry()
    return geo.x(), geo.y(), geo.width(), geo.height()


def measure_screens() -> dict:
    """Zmeri vsechny pripojene obrazovky.

    Vrati dict:
      screens: [{index, x, y, width, height (logicke),
                 physical_width, physical_height (skutecne pixely),
                 primary, dpr}]
      virtual: (x, y, w, h) pres vsechny monitory (logicke souradnice)
      primary: (w, h) fyzicke pixely primarni obrazovky
    """
    info = {"screens": [], "virtual": (0, 0, 0, 0), "primary": (0, 0)}
    try:
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
    # Fallback pres WinAPI (vraci fyzicke pixely)
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
