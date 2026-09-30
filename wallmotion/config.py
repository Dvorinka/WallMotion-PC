"""Application config file location (platform-specific, see wallmotion.paths)."""

from __future__ import annotations

from wallmotion.paths import config_path

# Kept as a module constant for backward compatibility (ui.py imports it).
CONFIG_PATH = str(config_path())
