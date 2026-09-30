"""Platform backend seam: wallpaper interface for individual OSes.

Windows backend uses the existing GDI/WorkerW trick (wallmotion.win32).
Linux/macOS backends will be added here without touching the rest of the app:
UI, downloads, config and languages are already multiplatform today.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod


class WallpaperBackend(ABC):
    """Interface every platform backend must implement."""

    name: str = "base"

    @abstractmethod
    def set_static_wallpaper(self, image_path: str) -> None:
        """Set a static image as the desktop wallpaper."""

    @abstractmethod
    def measure_screens(self) -> dict:
        """Measure screens (same format as wallmotion.screens)."""


def get_backend() -> WallpaperBackend:
    """Return the backend for the current OS. Unknown OS raises an exception."""
    if sys.platform == "win32":
        from wallmotion.platform.windows import WindowsBackend
        return WindowsBackend()
    raise NotImplementedError(
        f"Platforma {sys.platform} zatim nema backend (viz TODO.md)"
    )
