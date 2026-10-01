"""Per-wallpaper volume memory: remember mute/volume for each file.

Pure helpers (no Qt) operating on a plain dict stored in the config
under "volumes": {path: {"volume": 0-100, "muted": bool}}. Oldest
entries are trimmed so the config never grows without bounds.
"""

from __future__ import annotations

MAX_ENTRIES = 100
DEFAULT_VOLUME = 30
DEFAULT_MUTED = True


def lookup(store: dict | None, path: str) -> dict | None:
    """Settings remembered for path, or None. Never raises."""
    try:
        if not path or not isinstance(store, dict):
            return None
        entry = store.get(path)
        if not isinstance(entry, dict):
            return None
        return {
            "volume": max(0, min(100, int(entry.get("volume", DEFAULT_VOLUME)))),
            "muted": bool(entry.get("muted", DEFAULT_MUTED)),
        }
    except Exception:
        return None


def remember(store: dict | None, path: str, volume: int, muted: bool,
             limit: int = MAX_ENTRIES) -> dict:
    """Store settings for path as most-recent, trim oldest. Never raises."""
    try:
        store = dict(store) if isinstance(store, dict) else {}
    except Exception:
        store = {}
    try:
        if not path:
            return store
        if path in store:
            del store[path]
        store[path] = {
            "volume": max(0, min(100, int(volume))),
            "muted": bool(muted),
        }
        while len(store) > max(1, int(limit)):
            store.pop(next(iter(store)))
    except Exception:
        pass
    return store
