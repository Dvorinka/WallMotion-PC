"""Update check: poll GitHub Releases, compare tags, throttle weekly.

Stdlib only (urllib) so the logic is unit-testable. Network runs in a
small QThread worker; results come back over a Signal.
"""

from __future__ import annotations

import json
import time
import urllib.request

from PySide6.QtCore import QThread, Signal

LATEST_URL = ("https://api.github.com/repos/Jurek1357/WallMotion-PC"
              "/releases/latest")
CHECK_INTERVAL_SECONDS = 7 * 24 * 3600


def parse_version(tag: str) -> tuple:
    """'v1.0.4' -> (1, 0, 4). Unparseable -> (). Pure, unit-tested."""
    try:
        parts = str(tag).strip().lstrip("vV").split(".")
        return tuple(int(p) for p in parts if p.isdigit())
    except Exception:
        return ()


def is_newer(latest_tag: str, seen_tag: str | None) -> bool:
    """True when latest_tag is a newer version than seen_tag.

    Unknown seen_tag (first run) -> False: store silently, never nag
    on first launch.
    """
    try:
        if not latest_tag:
            return False
        if not seen_tag:
            return False
        latest, seen = parse_version(latest_tag), parse_version(seen_tag)
        return bool(latest) and bool(seen) and latest > seen
    except Exception:
        return False


def fetch_latest(timeout: float = 10.0) -> dict | None:
    """Download latest-release info. Returns {tag, url} or None."""
    try:
        request = urllib.request.Request(
            LATEST_URL, headers={"User-Agent": "WallMotion",
                                 "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
        tag = data.get("tag_name", "")
        url = data.get("html_url", "")
        if not tag:
            return None
        return {"tag": tag, "url": url}
    except Exception:
        return None


def should_auto_check(last_check: float | None,
                      now: float | None = None) -> bool:
    """Weekly throttle for the automatic check. Pure, unit-tested."""
    try:
        now = time.time() if now is None else float(now)
        if not last_check:
            return True
        return (now - float(last_check)) >= CHECK_INTERVAL_SECONDS
    except Exception:
        return True


class UpdateCheckWorker(QThread):
    """Fetch latest release in the background. Emits result dict or {}."""

    result = Signal(dict)

    def run(self):
        try:
            info = fetch_latest()
        except Exception:
            info = None
        try:
            self.result.emit(info or {})
        except Exception:
            pass
