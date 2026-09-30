"""User interface: DropZone, main window, entry-point main()."""

from __future__ import annotations

import json
import os
import sys

from PySide6.QtCore import QLoggingCategory, Qt, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from wallmotion import screens
from wallmotion.config import CONFIG_PATH
from wallmotion.i18n import (
    ACCENT,
    CURRENT_THEME,
    LANGS,
    STRINGS,
    THEMES,
    T,
    build_stylesheet,
)
from wallmotion.linux_video import LinuxVideoWallpaper
from wallmotion.platform import get_backend
from wallmotion.utils import DEBUG_LOG, _asset_path, _quiet_ffmpeg, debug_log
from wallmotion.video import VideoWallpaperWindow
from wallmotion.wallpaper import (
    IMAGE_EXTS,
    VIDEO_EXTS,
    fit_image_to_screen,
    get_current_wallpaper,
    set_static_wallpaper,
)
from wallmotion.youtube import (
    YT_DIR,
    DownloadWorker,
    PlaylistFetchWorker,
    is_playlist_url,
    is_valid_youtube_url,
)


class DropZone(QFrame):
    file_dropped = Signal(str)
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setFixedHeight(150)
        self.setCursor(Qt.PointingHandCursor)
        self._has_file = False
        self._hint = ""
        self._set_style(T("card"), T("border"))

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(self.icon_label)
        self._show_system_icon(QStyle.StandardPixmap.SP_DialogOpenButton)

        self.text_label = QLabel()
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setStyleSheet(f"color: {T('dim')}; font-size: 12px; background: transparent;")
        layout.addWidget(self.text_label)
        self.set_hint(STRINGS["cs"]["drop_hint"])

    def _set_style(self, color, border):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border: 2px dashed {border};
                border-radius: 12px;
            }}
        """)

    def _show_system_icon(self, which) -> None:
        """Native Windows-style system icon instead of emoji (QLabel with pixmap)."""
        try:
            pm = self.style().standardIcon(which).pixmap(52, 52)
            if not pm.isNull():
                self.icon_label.setPixmap(pm)
                return
        except Exception:
            pass
        self.icon_label.clear()

    def set_hint(self, text: str):
        self._hint = text
        if not self._has_file:
            self.text_label.setText(text)

    def refresh_style(self):
        self.text_label.setStyleSheet(
            f"color: {T('dim')}; font-size: 12px; background: transparent;"
        )
        self.icon_label.setStyleSheet("background: transparent;")
        self._set_style(T("card"), ACCENT if self._has_file else T("border"))

    def set_file(self, path: str):
        self._has_file = True
        name = os.path.basename(path)
        ext = os.path.splitext(path)[1].lower()
        if ext in IMAGE_EXTS:
            pix = QPixmap(path)
            if not pix.isNull():
                self.icon_label.setPixmap(
                    pix.scaledToHeight(70, Qt.SmoothTransformation)
                )
            else:
                self._show_system_icon(QStyle.StandardPixmap.SP_FileIcon)
        else:
            self._show_system_icon(QStyle.StandardPixmap.SP_MediaPlay)
            self.icon_label.setStyleSheet("background: transparent;")
        self.text_label.setText(name)
        self._set_style(T("card"), ACCENT)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_style(T("card_hover"), ACCENT)

    def dragLeaveEvent(self, event):
        self._set_style(T("card"), T("border"))

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.file_dropped.emit(path)

    def mousePressEvent(self, event):
        self.clicked.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Wallpaper")
        self.setFixedSize(430, 672)

        self.video_window = None
        self.selected_path = None
        try:
            self.original_wallpaper = get_current_wallpaper()
        except Exception:
            self.original_wallpaper = ""  # non-Windows: no wallpaper to restore
        self.screen_info = screens.measure_screens()
        self.monitors = screens.get_physical_monitors()
        self.monitor_choice = "all"  # "all" or physical monitor index
        # Platform backend (Linux: session renderer; None = unsupported).
        self._is_windows = sys.platform == "win32"
        self._linux_backend = None
        if not self._is_windows:
            try:
                self._linux_backend = get_backend()
            except Exception:
                self._linux_backend = None
            try:
                from wallmotion.platform.linux import describe_session
                debug_log(f"PLATFORM: {describe_session()} "
                          f"backend={getattr(self._linux_backend, 'name', None)}")
            except Exception:
                pass
        self.lang = "cs"
        self.theme = "dark"
        self.yt_worker = None
        self.pl_fetch_worker = None
        self._pl_queue = []
        self._pl_active = False
        self._pl_current = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        self.title_label = QLabel("Live Wallpaper")
        self.title_label.setObjectName("title")
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("subtitle")
        layout.addWidget(self.subtitle_label)

        self.screen_label = QLabel()
        self.screen_label.setObjectName("status")
        layout.addWidget(self.screen_label)

        # -- settings: language + theme -------------------------------------
        settings_row = QHBoxLayout()
        settings_row.setSpacing(8)
        self.lang_label = QLabel()
        settings_row.addWidget(self.lang_label)
        self.lang_combo = QComboBox()
        for code, name in LANGS.items():
            self.lang_combo.addItem(name, code)
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        settings_row.addWidget(self.lang_combo, 1)
        self.theme_label = QLabel()
        settings_row.addWidget(self.theme_label)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Tmavý", "dark")
        self.theme_combo.addItem("Světlý", "light")
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        settings_row.addWidget(self.theme_combo, 1)
        layout.addLayout(settings_row)

        # -- monitor selection ------------------------------------------------
        monitor_row = QHBoxLayout()
        monitor_row.setSpacing(8)
        self.monitor_label = QLabel()
        monitor_row.addWidget(self.monitor_label)
        self.monitor_combo = QComboBox()
        self.monitor_combo.currentIndexChanged.connect(self._on_monitor_changed)
        monitor_row.addWidget(self.monitor_combo, 1)
        layout.addLayout(monitor_row)

        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self._on_file_chosen)
        self.drop_zone.clicked.connect(self.browse_file)
        layout.addWidget(self.drop_zone)

        # -- YouTube link -------------------------------------------------
        yt_row = QHBoxLayout()
        yt_row.setSpacing(8)
        self.yt_input = QLineEdit()
        yt_row.addWidget(self.yt_input, 1)
        self.yt_button = QPushButton()
        self.yt_button.setObjectName("secondary")
        self.yt_button.clicked.connect(self.download_youtube)
        yt_row.addWidget(self.yt_button)
        layout.addLayout(yt_row)

        # -- downloaded videos folder -----------------------------------
        self.folder_button = QPushButton()
        self.folder_button.setObjectName("secondary")
        self.folder_button.clicked.connect(self.open_downloads_folder)
        layout.addWidget(self.folder_button)

        self.mute_checkbox = QCheckBox()
        self.mute_checkbox.setChecked(True)
        self.mute_checkbox.toggled.connect(self._on_mute_toggled)
        layout.addWidget(self.mute_checkbox)

        self.pause_fs_checkbox = QCheckBox()
        self.pause_fs_checkbox.setChecked(True)
        self.pause_fs_checkbox.toggled.connect(self._on_autopause_toggled)
        layout.addWidget(self.pause_fs_checkbox)

        self.pause_batt_checkbox = QCheckBox()
        self.pause_batt_checkbox.setChecked(False)
        self.pause_batt_checkbox.toggled.connect(self._on_autopause_toggled)
        layout.addWidget(self.pause_batt_checkbox)

        # -- video volume ---------------------------------------------
        vol_row = QHBoxLayout()
        vol_row.setSpacing(8)
        self.volume_label = QLabel()
        vol_row.addWidget(self.volume_label)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(30)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        vol_row.addWidget(self.volume_slider, 1)
        self.volume_value = QLabel("30%")
        self.volume_value.setFixedWidth(42)
        self.volume_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        vol_row.addWidget(self.volume_value)
        layout.addLayout(vol_row)

        self.apply_btn = QPushButton()
        self.apply_btn.clicked.connect(self.apply_wallpaper)
        layout.addWidget(self.apply_btn)

        self.measure_btn = QPushButton()
        self.measure_btn.setObjectName("secondary")
        self.measure_btn.clicked.connect(self.remeasure_screen)
        layout.addWidget(self.measure_btn)

        self.stop_btn = QPushButton()
        self.stop_btn.setObjectName("secondary")
        self.stop_btn.clicked.connect(self.stop_wallpaper)
        layout.addWidget(self.stop_btn)

        layout.addStretch()

        self.status_label = QLabel()
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self._init_tray()
        self._load_config()
        self.apply_theme(self.theme, save=False)
        self.retranslate()

    # -- tray ---------------------------------------------------------
    def _make_app_icon(self) -> QIcon:
        # Prefer icon from assets/icon.png file (monitor with play).
        try:
            p = _asset_path("icon.png")
            if os.path.exists(p):
                icon = QIcon(p)
                if not icon.isNull():
                    return icon
        except Exception:
            pass
        # Fallback: simple purple icon drawn programmatically so the tray
        # is never without an icon (fromTheme always returns null on Windows).
        try:
            pix = QPixmap(64, 64)
            pix.fill(Qt.transparent)
            from PySide6.QtGui import QColor, QFont, QPainter

            p = QPainter(pix)
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QColor(ACCENT))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(4, 4, 56, 56, 14, 14)
            p.setPen(QColor("#ffffff"))
            p.setFont(QFont("Segoe UI", 30, QFont.Bold))
            p.drawText(pix.rect(), Qt.AlignCenter, "W")
            p.end()
            return QIcon(pix)
        except Exception:
            try:
                from PySide6.QtWidgets import QStyle

                return self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            except Exception:
                return QIcon()

    def _init_tray(self):
        app_icon = self._make_app_icon()
        try:
            self.setWindowIcon(app_icon)
        except Exception:
            pass
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(app_icon)
        menu = QMenu()
        self.tray_show_action = QAction("Otevřít", self)
        self.tray_show_action.triggered.connect(self.showNormal)
        self.tray_quit_action = QAction("Ukončit", self)
        self.tray_quit_action.triggered.connect(self.quit_app)
        menu.addAction(self.tray_show_action)
        menu.addAction(self.tray_quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.showNormal() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )
        self.tray.show()

    def S(self) -> dict:
        return STRINGS.get(self.lang, STRINGS["cs"])

    # -- config ---------------------------------------------------------
    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, encoding="utf-8") as f:
                    cfg = json.load(f)
                lang = cfg.get("lang", "cs")
                if lang in STRINGS:
                    self.lang = lang
                theme = cfg.get("theme", "dark")
                if theme in THEMES:
                    self.theme = theme
                try:
                    self.mute_checkbox.setChecked(bool(cfg.get("muted", True)))
                except Exception:
                    pass
                try:
                    self.pause_fs_checkbox.setChecked(
                        bool(cfg.get("pause_fullscreen", True))
                    )
                    self.pause_batt_checkbox.setChecked(
                        bool(cfg.get("pause_battery", False))
                    )
                except Exception:
                    pass
                try:
                    mon = cfg.get("monitor", "all")
                    if mon != "all":
                        mon = int(mon)
                    self.monitor_choice = mon
                except Exception:
                    self.monitor_choice = "all"
                try:
                    self.volume_slider.blockSignals(True)
                    self.volume_slider.setValue(int(cfg.get("volume", 30)))
                    self.volume_slider.blockSignals(False)
                    self.volume_value.setText(f"{self.volume_slider.value()}%")
                except Exception:
                    pass
                path = cfg.get("last_path")
                if path and os.path.exists(path):
                    self.selected_path = path
                    self.drop_zone.set_file(path)
            except Exception:
                pass
        # set combo boxes without emitting signals
        try:
            self.lang_combo.blockSignals(True)
            self.lang_combo.setCurrentIndex(list(LANGS).index(self.lang))
            self.lang_combo.blockSignals(False)
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentIndex(0 if self.theme == "dark" else 1)
            self.theme_combo.blockSignals(False)
        except Exception:
            pass

    def _save_config(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "last_path": self.selected_path,
                    "lang": self.lang,
                    "theme": self.theme,
                    "muted": self.mute_checkbox.isChecked(),
                    "volume": self.volume_slider.value(),
                    "pause_fullscreen": self.pause_fs_checkbox.isChecked(),
                    "pause_battery": self.pause_batt_checkbox.isChecked(),
                    "monitor": self.monitor_choice,
                }, f)
        except Exception:
            pass

    def _on_mute_toggled(self, checked: bool):
        """F4: save the option and immediately toggle sound of the running wallpaper."""
        self._save_config()
        try:
            if self.video_window is not None:
                self.video_window.set_muted(bool(checked))
        except Exception:
            pass

    def _on_autopause_toggled(self, _checked: bool):
        """Save rules and apply them to the running wallpaper immediately."""
        self._save_config()
        try:
            if self.video_window is not None:
                self.video_window.set_auto_pause(
                    self.pause_fs_checkbox.isChecked(),
                    self.pause_batt_checkbox.isChecked(),
                )
        except Exception:
            pass

    def _on_volume_changed(self, value: int):
        """Save the volume and immediately apply it to the running wallpaper."""
        self.volume_value.setText(f"{int(value)}%")
        self._save_config()
        try:
            if self.video_window is not None:
                self.video_window.set_volume(float(value) / 100.0)
        except Exception:
            pass

    # -- theme + language ---------------------------------------------------------
    def apply_theme(self, theme: str, save: bool = True):
        if theme not in THEMES:
            theme = "dark"
        self.theme = theme
        CURRENT_THEME.clear()
        CURRENT_THEME.update(THEMES[theme])
        try:
            QApplication.instance().setStyleSheet(build_stylesheet(theme))
        except Exception:
            pass
        try:
            self.drop_zone.refresh_style()
        except Exception:
            pass
        if save:
            self._save_config()

    def _on_theme_changed(self, _index: int):
        theme = self.theme_combo.currentData() or "dark"
        self.apply_theme(theme)
        self.retranslate()

    def _on_lang_changed(self, _index: int):
        lang = self.lang_combo.currentData() or "cs"
        if lang not in STRINGS:
            lang = "cs"
        self.lang = lang
        self._save_config()
        self.retranslate()

    def retranslate(self):
        s = self.S()
        self.subtitle_label.setText(s["subtitle"])
        self.lang_label.setText(s["lang_label"])
        self.theme_label.setText(s["theme_label"])
        # theme combo box texts
        try:
            self.theme_combo.blockSignals(True)
            self.theme_combo.setItemText(0, s["theme_dark"])
            self.theme_combo.setItemText(1, s["theme_light"])
            self.theme_combo.blockSignals(False)
        except Exception:
            pass
        self.drop_zone.set_hint(s["drop_hint"])
        self.mute_checkbox.setText(s["mute"])
        self.pause_fs_checkbox.setText(s["pause_fullscreen"])
        self.pause_batt_checkbox.setText(s["pause_battery"])
        self.monitor_label.setText(s["monitor_label"])
        self._refresh_monitor_combo()
        self.volume_label.setText(s["volume_label"])
        self.apply_btn.setText(s["apply"])
        self.measure_btn.setText(s["measure"])
        self.stop_btn.setText(s["stop"])
        self.yt_input.setPlaceholderText(s["yt_placeholder"])
        self.yt_button.setText(s["yt_button"])
        self.folder_button.setText(s["open_folder"])
        if not self.status_label.text():
            self.status_label.setText(s["ready"])
        try:
            self.tray_show_action.setText(s["open_tray"])
            self.tray_quit_action.setText(s["quit_tray"])
        except Exception:
            pass
        self._refresh_screen_label()

    # -- YouTube ---------------------------------------------------------
    def download_youtube(self):
        s = self.S()
        url = self.yt_input.text().strip()
        if not url:
            self.status_label.setText(s["warn_nofile_m"])
            return
        # F1: validate the URL before passing it to yt-dlp.
        if not is_valid_youtube_url(url):
            self.status_label.setText(
                s["yt_error"].format(e=s["yt_invalid_url"])
            )
            return
        if is_playlist_url(url):
            self._fetch_playlist(url)
            return
        self._pl_active = False
        self._pl_queue = []
        self._pl_current = None
        self._start_download_worker(url)

    def _start_download_worker(self, url: str):
        """Start DownloadWorker for one video (single URL or queue item)."""
        s = self.S()
        if self.yt_worker is not None and self.yt_worker.isRunning():
            return
        self.yt_button.setEnabled(False)
        self.status_label.setText(s["yt_downloading"].format(p="0%"))
        debug_log(f"YT: stahuji {url}")
        self.yt_worker = DownloadWorker(url, self)
        self.yt_worker.progress.connect(self._on_yt_progress)
        self.yt_worker.finished.connect(self._on_yt_finished)
        self.yt_worker.error.connect(self._on_yt_error)
        self.yt_worker.finished.connect(lambda _p: self.yt_button.setEnabled(True))
        self.yt_worker.error.connect(lambda _e: self.yt_button.setEnabled(True))
        self.yt_worker.start()

    def _fetch_playlist(self, url: str):
        """Load playlist entries on a background thread, then show picker."""
        if self.yt_worker is not None and self.yt_worker.isRunning():
            return
        if self.pl_fetch_worker is not None and self.pl_fetch_worker.isRunning():
            return
        self.yt_button.setEnabled(False)
        self.status_label.setText(self.S()["yt_playlist_loading"])
        debug_log(f"YT playlist: nacitam {url}")
        self.pl_fetch_worker = PlaylistFetchWorker(url, self)
        self.pl_fetch_worker.loaded.connect(self._on_playlist_loaded)
        self.pl_fetch_worker.error.connect(self._on_playlist_error)
        self.pl_fetch_worker.loaded.connect(
            lambda _e: self.yt_button.setEnabled(True)
        )
        self.pl_fetch_worker.error.connect(
            lambda _e: self.yt_button.setEnabled(True)
        )
        self.pl_fetch_worker.start()

    def _on_playlist_loaded(self, entries: list):
        s = self.S()
        debug_log(f"YT playlist: nacteno {len(entries)} polozek")
        dialog = QDialog(self)
        dialog.setWindowTitle(s["yt_playlist_title"])
        dialog.setMinimumWidth(360)
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget(dialog)
        list_widget.setSelectionMode(QListWidget.MultiSelection)
        for e in entries:
            try:
                item = QListWidgetItem(str(e.get("title") or e.get("id")))
                item.setData(Qt.UserRole, e.get("url"))
                list_widget.addItem(item)
            except Exception:
                continue
        layout.addWidget(list_widget)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            self.status_label.setText(s["ready"])
            return
        urls = []
        for item in list_widget.selectedItems():
            try:
                u = item.data(Qt.UserRole)
                if u:
                    urls.append(u)
            except Exception:
                continue
        if not urls:
            self.status_label.setText(s["ready"])
            return
        # Sequential queue: each item keeps the 500 MB + H.264/1080p guards
        # of DownloadWorker; last downloaded video ends up as wallpaper.
        total = len(urls)
        self._pl_queue = [(i + 1, total, u) for i, u in enumerate(urls[1:])]
        self._pl_active = True
        self._pl_current = (1, total)
        self.status_label.setText(s["yt_queue_progress"].format(i=1, n=total))
        self._start_download_worker(urls[0])

    def _on_playlist_error(self, err: str):
        debug_log(f"YT playlist CHYBA: {err}")
        if err == "EMPTY_PLAYLIST":
            err = self.S()["yt_playlist_empty"]
        self.status_label.setText(self.S()["yt_error"].format(e=err))

    def _on_queue_item_done(self):
        """Start next queued playlist item, if any."""
        if not self._pl_active:
            return
        if self._pl_queue:
            i, n, url = self._pl_queue.pop(0)
            self._pl_current = (i, n)
            self.status_label.setText(
                self.S()["yt_queue_progress"].format(i=i, n=n)
            )
            self._start_download_worker(url)
        else:
            self._pl_active = False
            self._pl_current = None

    def _on_yt_progress(self, pct: str):
        if self._pl_active and self._pl_current:
            i, n = self._pl_current
            self.status_label.setText(
                self.S()["yt_queue_progress"].format(i=i, n=n)
                + " " + self.S()["yt_downloading"].format(p=pct)
            )
        else:
            self.status_label.setText(self.S()["yt_downloading"].format(p=pct))

    def _on_yt_finished(self, path: str):
        s = self.S()
        debug_log(f"YT: stazeno {path}")
        self.status_label.setText(s["yt_done"])
        self._on_file_chosen(path)
        # set as wallpaper right after download
        self.apply_wallpaper()
        # playlist queue: continue with the next selected item
        self._on_queue_item_done()

    def _on_yt_error(self, err: str):
        debug_log(f"YT CHYBA: {err}")
        if err == "NEED_FFMPEG":
            err = self.S()["yt_need_ffmpeg"]
        self.status_label.setText(self.S()["yt_error"].format(e=err))
        # playlist queue: skip the broken video, keep going
        self._on_queue_item_done()

    def _refresh_linux_backend(self):
        """(Re-)detect the Linux session backend. None when unsupported."""
        if self._is_windows:
            return None
        if self._linux_backend is None:
            try:
                self._linux_backend = get_backend()
            except Exception:
                self._linux_backend = None
        return self._linux_backend

    def _start_linux_video(self, s, pw, ph):
        """Video wallpaper on Linux via the session backend."""
        from wallmotion.platform.linux import describe_session
        backend = self._refresh_linux_backend()
        if backend is None:
            self.status_label.setText(
                s["linux_no_backend"].format(s=describe_session()))
            return
        if getattr(backend, "name", "") == "gnome":
            QMessageBox.warning(
                self, s["linux_gnome_video_t"], s["linux_gnome_video_m"])
            self.status_label.setText(s["linux_gnome_video_m"])
            return
        self.video_window = LinuxVideoWallpaper(
            backend, self.selected_path, muted=self.mute_checkbox.isChecked(),
            volume=self.volume_slider.value() / 100.0,
            auto_pause_fullscreen=self.pause_fs_checkbox.isChecked(),
            auto_pause_battery=self.pause_batt_checkbox.isChecked(),
        )
        self.video_window.failed.connect(self._on_video_failed)
        if self.video_window.start():
            self.status_label.setText(s["vid_running"].format(w=pw, h=ph))
            self.tray.showMessage(
                s["app_name"], s["vid_started_msg"],
                QSystemTrayIcon.MessageIcon.Information, 3000
            )
        else:
            self.video_window.stop()
            self.video_window = None
            try:
                tools = ", ".join(backend.missing_tools()) or "?"
            except Exception:
                tools = "?"
            self.status_label.setText(s["linux_missing"].format(tools=tools))
            QMessageBox.warning(
                self, s["vid_fail_t"],
                s["linux_missing"].format(tools=tools),
            )

    def open_downloads_folder(self):
        """Open the downloaded videos folder in Explorer."""
        try:
            os.makedirs(YT_DIR, exist_ok=True)
        except Exception:
            pass
        try:
            os.startfile(YT_DIR)  # Windows
        except Exception:
            try:
                from PySide6.QtCore import QDesktopServices
                QDesktopServices.openUrl(QUrl.fromLocalFile(YT_DIR))
            except Exception:
                pass

    # -- screen ---------------------------------------------------------
    def _refresh_screen_label(self):
        s = self.S()
        screens_info = self.screen_info.get("screens", [])
        pw, ph = self.screen_info.get("primary", (0, 0))
        if not screens_info:
            self.screen_label.setText(s["screen_unknown"])
            return
        if len(screens_info) == 1:
            self.screen_label.setText(s["screen_one"].format(w=pw, h=ph))
        else:
            parts = " + ".join(
                f"{x['physical_width']}×{x['physical_height']}" for x in screens_info
            )
            self.screen_label.setText(
                s["screen_multi"].format(n=len(screens_info), parts=parts, w=pw, h=ph)
            )

    def remeasure_screen(self):
        self.screen_info = screens.measure_screens()
        self.monitors = screens.get_physical_monitors()
        self._refresh_screen_label()
        self._refresh_monitor_combo()
        pw, ph = self.screen_info.get("primary", (0, 0))
        self.status_label.setText(self.S()["measured"].format(w=pw, h=ph))

    def _refresh_monitor_combo(self):
        """Rebuild monitor selector (all + physical monitors)."""
        s = self.S()
        try:
            self.monitor_combo.blockSignals(True)
            self.monitor_combo.clear()
            self.monitor_combo.addItem(s["monitor_all"], "all")
            for m in self.monitors:
                try:
                    label = f"Monitor {m['index'] + 1} ({m['w']}x{m['h']})"
                    if m.get("primary"):
                        label += f" - {s['monitor_primary']}"
                    self.monitor_combo.addItem(label, m["index"])
                except Exception:
                    continue
            idx = 0
            if self.monitor_choice != "all":
                for i in range(self.monitor_combo.count()):
                    if self.monitor_combo.itemData(i) == self.monitor_choice:
                        idx = i
                        break
                else:
                    self.monitor_choice = "all"
            self.monitor_combo.setCurrentIndex(idx)
        except Exception:
            pass
        finally:
            try:
                self.monitor_combo.blockSignals(False)
            except Exception:
                pass

    def _on_monitor_changed(self, index: int):
        try:
            choice = self.monitor_combo.itemData(index)
            self.monitor_choice = choice if choice is not None else "all"
        except Exception:
            self.monitor_choice = "all"
        self._save_config()

    def _selected_monitor(self) -> dict | None:
        """Chosen physical monitor {x, y, w, h}, or None for all monitors."""
        if self.monitor_choice == "all":
            return None
        try:
            for m in self.monitors:
                if m.get("index") == self.monitor_choice:
                    return dict(m)
        except Exception:
            pass
        return None

    # -- UI actions ---------------------------------------------------------
    def browse_file(self):
        s = self.S()
        filters = (
            "Obrázky a videa / Images & videos "
            "(*.jpg *.jpeg *.png *.bmp *.gif *.mp4 *.avi *.mkv *.mov *.wmv *.webm)"
        )
        path, _ = QFileDialog.getOpenFileName(self, s["apply"], "", filters)
        if path:
            self._on_file_chosen(path)

    def _on_file_chosen(self, path: str):
        s = self.S()
        ext = os.path.splitext(path)[1].lower()
        if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
            QMessageBox.warning(self, s["warn_unsupported_t"], s["warn_unsupported_m"])
            return
        self.selected_path = path
        self.drop_zone.set_file(path)
        self.status_label.setText(s["file_selected"])

    def apply_wallpaper(self):
        s = self.S()
        if not self.selected_path:
            QMessageBox.warning(self, s["warn_nofile_t"], s["warn_nofile_m"])
            return

        if self.video_window is not None:
            self.video_window.stop()
            self.video_window = None

        ext = os.path.splitext(self.selected_path)[1].lower()

        # Always fit the background to the measured screen size.
        self.screen_info = screens.measure_screens()
        self.monitors = screens.get_physical_monitors()
        self._refresh_screen_label()
        self._refresh_monitor_combo()
        mon = self._selected_monitor()
        if mon:
            pw, ph = mon["w"], mon["h"]
        else:
            pw, ph = self.screen_info.get("primary", (0, 0))
        debug_log(f"APPLY: path={self.selected_path} ext={ext} screen={pw}x{ph}")

        if ext in IMAGE_EXTS:
            fitted = fit_image_to_screen(self.selected_path, pw, ph)
            if self._is_windows:
                set_static_wallpaper(fitted)
            else:
                from wallmotion.platform.linux import describe_session
                backend = self._refresh_linux_backend()
                if backend is None:
                    self.status_label.setText(
                        s["linux_no_backend"].format(s=describe_session()))
                    return
                if not backend.set_image(fitted):
                    try:
                        tools = ", ".join(backend.missing_tools()) or "?"
                    except Exception:
                        tools = "?"
                    self.status_label.setText(
                        s["linux_missing"].format(tools=tools))
                    return
            self.status_label.setText(s["img_set"].format(w=pw, h=ph))
        elif ext in VIDEO_EXTS:
            if not self._is_windows:
                self._start_linux_video(s, pw, ph)
                self._save_config()
                return
            self.video_window = VideoWallpaperWindow(
                self.selected_path, muted=self.mute_checkbox.isChecked(),
                volume=self.volume_slider.value() / 100.0,
                auto_pause_fullscreen=self.pause_fs_checkbox.isChecked(),
                auto_pause_battery=self.pause_batt_checkbox.isChecked(),
                monitor=mon,
            )
            self.video_window.failed.connect(self._on_video_failed)
            if self.video_window.start():
                self.status_label.setText(s["vid_running"].format(w=pw, h=ph))
                self.tray.showMessage(
                    s["app_name"], s["vid_started_msg"],
                    QSystemTrayIcon.MessageIcon.Information, 3000
                )
            else:
                self.video_window.stop()
                self.video_window = None
                self.status_label.setText(s["vid_fail_m"].format(log=DEBUG_LOG))
                QMessageBox.warning(
                    self, s["vid_fail_t"],
                    s["vid_fail_m"].format(log=DEBUG_LOG),
                )
                return
        else:
            return

        self._save_config()

    def _on_video_failed(self, reason: str):
        s = self.S()
        debug_log(f"VIDEO FAILED: {reason}")
        if self.video_window is not None:
            try:
                self.video_window.failed.disconnect(self._on_video_failed)
            except Exception:
                pass
            self.video_window = None
        if reason == "decode":
            self.status_label.setText(s["vid_decode_m"])
            QMessageBox.warning(self, s["vid_decode_t"], s["vid_decode_m"])
        else:
            self.status_label.setText(s["vid_fail_m"].format(log=DEBUG_LOG))

    def stop_wallpaper(self):
        if self.video_window is not None:
            self.video_window.stop()
            self.video_window = None
        if self._is_windows:
            if self.original_wallpaper:
                set_static_wallpaper(self.original_wallpaper)
        else:
            try:
                if self._linux_backend is not None:
                    self._linux_backend.stop()
            except Exception:
                pass
        self.status_label.setText(self.S()["restored"])

    def closeEvent(self, event):
        s = self.S()
        event.ignore()
        self.hide()
        self.tray.showMessage(
            s["app_name"], s["hidden_tray_msg"],
            QSystemTrayIcon.MessageIcon.Information, 2000
        )

    def quit_app(self):
        if self.video_window is not None:
            self.video_window.stop()
        QApplication.quit()


def main():
    # Qt 6 sets DPI awareness (Per-Monitor V2) by itself.
    # Manual SetProcessDpiAwareness would throw "Access denied",
    # so we deliberately do NOT call it here.
    # Silence chatty FFmpeg logs (Input #0, MFT, ...). They are not errors,
    # just decoding info, so hide them to keep the console clean.
    # Qt categories (via QT_LOGGING_RULES) + native av_log level (directly in FFmpeg).
    os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg=false")
    try:
        QLoggingCategory.setFilterRules("qt.multimedia.ffmpeg=false")
    except Exception:
        pass
    _quiet_ffmpeg()
    try:
        from wallmotion.paths import ensure_dirs
        ensure_dirs()
    except Exception:
        pass
    try:
        with open(DEBUG_LOG, "w", encoding="utf-8") as f:
            f.write("=== Live Wallpaper start ===\n")
    except Exception:
        pass
    debug_log("APP start")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(build_stylesheet("dark"))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
