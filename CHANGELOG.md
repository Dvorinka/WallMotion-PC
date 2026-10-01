# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.5] - 2026-10-01

Linux support v1, CLI, AppImage packaging and all P1/P2 features below.

### Added
- Open-source project files: MIT license, contributing guide, code of
  conduct, security policy, issue/PR templates, CI and release workflows.
- Platform paths helper (`wallmotion/paths.py`): XDG directories
  (`~/.config`, `~/.local/share`, `~/.local/state`) on Linux, legacy
  locations kept on Windows.
- UI strings extracted into locale files (`locales/cs.json`,
  `locales/en.json`) loaded by `wallmotion/i18n.py`.
- Auto-pause rules: video pauses when a fullscreen app runs (games)
  and optionally on battery power; both checkboxes in the UI,
  remembered between launches.
- YouTube playlist support: `/playlist` links open a picker dialog,
  selected videos download sequentially (500 MB cap and H.264/1080p
  guards apply per item).
- Multi-monitor selection: video wallpaper (and image fit) can target
  one monitor or span all; choice remembered between launches.
- Linux support v1: session detection (`XDG_SESSION_TYPE` /
  `XDG_CURRENT_DESKTOP`), image backends (`feh`, `swww`, `gsettings`,
  `plasma-apply-wallpaperimage`), video via `mpvpaper` / `xwinwrap`+`mpv`,
  live volume/mute/pause over mpv JSON IPC, sysfs battery sensor,
  missing-tool messages in the UI. GNOME-Wayland video remains
  unsupported (Hanabi extension needed). Not yet tested on hardware.
- Linux per-monitor video: chosen monitor drives `xwinwrap -g WxH+X+Y`
  on X11 (monitor list from Qt data); mpvpaper stays all-outputs.
- CLI: `wallmotion --set FILE --stop --mute/--unmute --volume N`
  with single-instance forwarding to the running app.
- Update check: weekly GitHub Releases poll with tray notice,
  manual check in the tray menu.
- Linux packaging: AppImage built in CI (`appimage.yml`) and attached
  to tag Releases next to the Windows .exe.
- Per-wallpaper volume memory: mute/volume is remembered for each file
  (last 100) and restored on selection.
- Wallpaper rotation: queue of local images/videos with 1 min–1 h
  interval and shuffle, persisted between launches.
- Code comments translated to English (user-facing strings stay
  Czech/English in `locales/`).

### Fixed
- Linux CI: `wallmotion/screens.py` imports Qt lazily so pure logic
  and tests work headless (no `libEGL` needed).

## [1.0.0] - 2026-09-14

First stable release.

### Added
- Static image wallpaper auto-fitted to measured screen resolution.
- Video wallpaper behind desktop icons (Windows 10 + Windows 11
  "raised desktop"), click-through and focus-safe.
- YouTube download in background (H.264 only, up to 1080p, max 500 MB,
  always with audio) via yt-dlp; bundled ffmpeg via imageio-ffmpeg.
- Mute checkbox and live volume slider.
- Dark/light themes, Czech/English UI, persisted config.
- Multi-monitor measurement (physical pixels, HiDPI aware), system tray,
  debug log at `%TEMP%\live_wallpaper_debug.log`.
- Standalone `WallMotion.exe` (PyInstaller, ~65 MB).

[Unreleased]: https://github.com/Jurek1357/WallMotion-PC/compare/v1.0.5...HEAD
[1.0.5]: https://github.com/Jurek1357/WallMotion-PC/releases/tag/v1.0.5
[1.0.0]: https://github.com/Jurek1357/WallMotion-PC/releases/tag/v1.0.0
