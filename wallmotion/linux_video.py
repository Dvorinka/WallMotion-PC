"""Video wallpaper on Linux: one mpv process driven by a platform backend.

Same control surface as VideoWallpaperWindow (start/stop/set_muted/
set_volume/failed signal) plus pause()/resume() for the autopause rules.
Playback state changes (mute/volume/pause) go through mpv JSON IPC,
so nothing restarts - the video keeps playing underneath.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from wallmotion.autopause import (
    POLL_INTERVAL_MS,
    RESUME_AFTER_CLEAN_POLLS,
    is_fullscreen_app_active,
    is_on_battery,
    should_pause,
)
from wallmotion.utils import debug_log


class LinuxVideoWallpaper(QObject):
    """Thin Qt wrapper around a LinuxProcessBackend video process."""

    failed = Signal(str)

    def __init__(self, backend, video_path: str, muted: bool = True,
                 volume: float = 0.3, auto_pause_fullscreen: bool = True,
                 auto_pause_battery: bool = False, monitor: dict | None = None,
                 parent=None):
        super().__init__(parent)
        self._backend = backend
        self.video_path = video_path
        self._muted = bool(muted)
        self._volume = max(0.0, min(1.0, float(volume)))
        self._monitor = dict(monitor) if monitor else None
        self._pause_on_fullscreen = bool(auto_pause_fullscreen)
        self._pause_on_battery = bool(auto_pause_battery)
        self._timer = None
        self._autopaused = False
        self._clean_polls = 0
        self._running = False
        self._user_paused = False  # manual Pause button (autopause must not override)

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        try:
            self._backend.set_muted(self._muted)
        except Exception:
            pass

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, float(volume)))
        try:
            if not self._muted:
                self._backend.set_volume(self._volume)
        except Exception:
            pass

    def set_auto_pause(self, fullscreen: bool, battery: bool) -> None:
        self._pause_on_fullscreen = bool(fullscreen)
        self._pause_on_battery = bool(battery)
        self._clean_polls = 0
        try:
            if self._pause_on_fullscreen or self._pause_on_battery:
                self._start_timer()
            else:
                self._stop_timer()
                if self._autopaused and not self._user_paused:
                    self.resume("rules-off")
        except Exception as e:
            debug_log(f"AUTOPAUSE: set_auto_pause error: {e!r}")

    def pause(self) -> None:
        try:
            self._backend.set_paused(True)
            self._autopaused = True
            self._clean_polls = 0
        except Exception as e:
            debug_log(f"AUTOPAUSE: pause error: {e!r}")

    def set_user_paused(self, paused: bool) -> None:
        """Manual Pause button: freeze the frame, keep the process."""
        self._user_paused = bool(paused)
        try:
            self._backend.set_paused(self._user_paused)
            debug_log(f"user paused={self._user_paused}")
        except Exception as e:
            debug_log(f"user pause error: {e!r}")

    def is_user_paused(self) -> bool:
        return bool(self._user_paused)

    def resume(self, reason: str = "") -> None:
        try:
            self._backend.set_paused(False)
            self._autopaused = False
            self._clean_polls = 0
            debug_log(f"AUTOPAUSE: resuming ({reason})")
        except Exception as e:
            debug_log(f"AUTOPAUSE: resume error: {e!r}")

    def start(self) -> bool:
        debug_log(f"START(linux): path={self.video_path} "
                  f"backend={getattr(self._backend, 'name', '?')}")
        try:
            geometry = None
            if self._monitor and getattr(self._backend, "name", "") == "x11":
                from wallmotion.platform.linux import xwinwrap_geometry
                geometry = xwinwrap_geometry(self._monitor)
            ok = self._backend.set_video(
                self.video_path, self._muted, self._volume,
                geometry=geometry)
        except Exception as e:
            debug_log(f"START(linux): backend exception: {e!r}")
            return False
        if not ok:
            try:
                missing = self._backend.missing_tools()
            except Exception:
                missing = []
            debug_log(f"START(linux): backend refused (missing={missing})")
            return False
        self._running = True
        if self._pause_on_fullscreen or self._pause_on_battery:
            self._start_timer()
        try:
            QTimer.singleShot(8000, self._check_progress)
        except Exception:
            pass
        return True

    def stop(self) -> None:
        self._stop_timer()
        self._autopaused = False
        self._user_paused = False
        self._running = False
        try:
            self._backend.stop()
        except Exception:
            pass
        try:
            self.deleteLater()
        except Exception:
            pass

    def _check_progress(self):
        # The child is an external process: if it died within 8 s,
        # the tool or the file is unusable - report like the Qt watchdog.
        try:
            if not self._running:
                return
            alive = False
            try:
                alive = self._backend._alive()
            except Exception:
                alive = True
            if not alive:
                debug_log("WATCHDOG(linux): child died early -> giving up")
                self.failed.emit("decode")
                self.stop()
        except Exception as e:
            debug_log(f"WATCHDOG(linux) exception: {e!r}")

    def _start_timer(self) -> None:
        try:
            if self._timer is None:
                self._timer = QTimer(self)
                self._timer.timeout.connect(self._autopause_tick)
            if not self._timer.isActive():
                self._timer.start(POLL_INTERVAL_MS)
        except Exception as e:
            debug_log(f"AUTOPAUSE: timer start failed: {e!r}")

    def _stop_timer(self) -> None:
        try:
            if self._timer is not None:
                self._timer.stop()
        except Exception:
            pass

    def _autopause_tick(self) -> None:
        try:
            if not (self._pause_on_fullscreen or self._pause_on_battery):
                return
            if not self._running:
                return
            if self._user_paused:
                return  # manual pause wins, do not touch playback
            try:
                fullscreen = (
                    is_fullscreen_app_active() if self._pause_on_fullscreen else False
                )
                battery = is_on_battery() if self._pause_on_battery else False
            except Exception:
                return
            want_pause = should_pause(
                fullscreen, battery,
                pause_on_fullscreen=self._pause_on_fullscreen,
                pause_on_battery=self._pause_on_battery,
            )
            if want_pause:
                if not self._autopaused:
                    debug_log(f"AUTOPAUSE: pausing "
                              f"(fullscreen={fullscreen} battery={battery})")
                    self.pause()
                return
            if self._autopaused:
                self._clean_polls += 1
                if self._clean_polls >= RESUME_AFTER_CLEAN_POLLS:
                    self.resume("clean")
        except Exception as e:
            debug_log(f"AUTOPAUSE: tick exception: {e!r}")
