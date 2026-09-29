from __future__ import annotations

import queue
import sys
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, QTimer, QUrl, Qt
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from panda import __version__
from panda.core.config import (
    ConfigStore,
    ProfileManager,
    UI_DEFAULTS,
    apply_response_preset,
    normalize_settings,
)
from panda.core.diagnostics import DiagnosticLog, format_diagnostics, system_snapshot
from panda.core.drivers import driver_status, install_or_repair_drivers, open_hidhide_client, set_launch_on_startup
from panda.core.engine import EngineWorker
from panda.ui.controller import ControllerPage
from panda.ui.dashboard import DashboardPage
from panda.ui.diagnostics import DiagnosticsPage
from panda.ui.profiles import ProfilesPage
from panda.ui.settings import AboutPage, PreferencesPage, ScreenPage, build_detection_page, build_response_page
from panda.ui.styles import stylesheet
from panda.ui.widgets import StatusBadge, app_icon

REPOSITORY = "https://github.com/moha700m/Panda"
PAGE_META = {
    "dashboard": ("Dashboard", "Engine health and current training session."),
    "screen": ("Screen", "Capture monitor, region and preview controls."),
    "detection": ("Detection", "Color filtering, target selection and tracking."),
    "response": ("Response", "Tune correction response and activation."),
    "controller": ("Controller", "Live XInput telemetry and button states."),
    "profiles": ("Profiles", "Save, organize and switch training profiles."),
    "diagnostics": ("Diagnostics", "System checks, installer actions and logs."),
    "settings": ("Settings", "Window behavior and appearance preferences."),
    "about": ("About", "Product and release information."),
}
NAV = (
    ("dashboard", "▦", "Dashboard"),
    ("screen", "▧", "Screen"),
    ("detection", "◉", "Detection"),
    ("response", "⌁", "Response"),
    ("controller", "◎", "Controller"),
    ("profiles", "▣", "Profiles"),
    ("diagnostics", "◌", "Diagnostics"),
    ("settings", "⚙", "Settings"),
    ("about", "ⓘ", "About"),
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_store = ConfigStore()
        self.profile_store = ProfileManager(self.config_store.root)
        old_config = self.config_store.load()
        had_profiles = bool(self.profile_store.list())
        self.profile_store.ensure_defaults()
        if not had_profiles:
            # Import the user's existing v1 settings into the new Default profile once.
            self.profile_store.save("Default", old_config)
        self.preferences = {key: old_config.get(key, value) for key, value in UI_DEFAULTS.items()}
        names = self.profile_store.list()
        preferred = self.preferences.get("last_profile", "Default")
        if not self.preferences.get("auto_load_last_profile", True) or preferred not in names:
            preferred = "Default"
        self.current_profile = preferred
        try:
            self.engine_settings = self.profile_store.load(preferred)
        except Exception:
            self.current_profile = "Default"
            self.engine_settings = self.profile_store.load("Default")
        self.settings = {**self.engine_settings, **self.preferences}
        self.events: queue.Queue = queue.Queue()
        self.worker: EngineWorker | None = None
        self.log_store = DiagnosticLog(self.config_store.root)
        self.log_store.write("Application started")
        self.runtime = EngineWorker._empty_telemetry()
        self.system = system_snapshot(self.engine_settings["slot"])
        self._last_preview_identity = None
        self._allow_close = False
        self._exit_requested = False
        self._tray: QSystemTrayIcon | None = None
        self._driver_thread: threading.Thread | None = None

        self.setWindowTitle(f"Panda Training Standalone {__version__}")
        self.setMinimumSize(1080, 690)
        self.resize(1280, 840)
        self._icon = QIcon(app_icon(self.preferences.get("accent_color", "#C7F36B")))
        self.setWindowIcon(self._icon)
        self._build_shell()
        self._wire_pages()
        self._sync_settings()
        self.profiles_page.set_profiles(self.profile_store.list(), self.current_profile)
        self.diagnostics_page.set_log(self.log_store.read())
        self._refresh_system()
        self._restore_geometry()
        self._setup_tray()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._persist)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(100)
        self._poll_timer.timeout.connect(self._poll_events)
        self._poll_timer.start()
        self._system_timer = QTimer(self)
        self._system_timer.setInterval(4000)
        self._system_timer.timeout.connect(self._refresh_system)
        self._system_timer.start()
        self._apply_theme()
        self.show_page("dashboard")
        if self.preferences.get("start_minimized"):
            QTimer.singleShot(0, self.showMinimized)

    def _build_shell(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(222)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 22, 14, 18)
        side_layout.setSpacing(12)
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(app_icon(self.preferences.get("accent_color", "#C7F36B")).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        brand.addWidget(logo)
        brand_text = QVBoxLayout()
        name = QLabel("PANDA")
        name.setObjectName("brand")
        sub = QLabel("TRAINING VISION")
        sub.setObjectName("eyebrow")
        brand_text.addWidget(name)
        brand_text.addWidget(sub)
        brand.addLayout(brand_text)
        brand.addStretch(1)
        side_layout.addLayout(brand)
        side_layout.addSpacing(12)
        product = QLabel("Training Vision Controller")
        product.setObjectName("muted")
        side_layout.addWidget(product)
        separator = QFrame()
        separator.setObjectName("divider")
        side_layout.addWidget(separator)
        side_layout.addSpacing(5)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, icon, label in NAV:
            button = QPushButton(f"{icon}    {label}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, page=key: self.show_page(page))
            self.nav_buttons[key] = button
            side_layout.addWidget(button)
        side_layout.addStretch(1)
        side_state = QLabel(f"VERSION  {__version__}")
        side_state.setObjectName("eyebrow")
        side_layout.addWidget(side_state)
        root.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(26, 22, 24, 14)
        content_layout.setSpacing(16)
        header = QHBoxLayout()
        title_column = QVBoxLayout()
        title_column.setSpacing(4)
        self.page_title = QLabel("Dashboard")
        self.page_title.setObjectName("pageTitle")
        self.page_description = QLabel(PAGE_META["dashboard"][1])
        self.page_description.setObjectName("muted")
        title_column.addWidget(self.page_title)
        title_column.addWidget(self.page_description)
        header.addLayout(title_column, 1)
        self.header_status = StatusBadge("SYSTEM CHECK")
        header.addWidget(self.header_status, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        content_layout.addLayout(header)

        self.stack = QStackedWidget()
        self.dashboard = DashboardPage()
        self.screen_page = ScreenPage()
        self.detection_page = build_detection_page()
        self.response_page = build_response_page()
        self.controller_page = ControllerPage()
        self.profiles_page = ProfilesPage()
        self.diagnostics_page = DiagnosticsPage()
        self.preferences_page = PreferencesPage()
        self.about_page = AboutPage(__version__, REPOSITORY)
        self.pages = {
            "dashboard": self.dashboard,
            "screen": self.screen_page,
            "detection": self.detection_page,
            "response": self.response_page,
            "controller": self.controller_page,
            "profiles": self.profiles_page,
            "diagnostics": self.diagnostics_page,
            "settings": self.preferences_page,
            "about": self.about_page,
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        content_layout.addWidget(self.stack, 1)
        self.statusBar().showMessage("Ready · hardware checks available in Diagnostics")
        root.addWidget(content, 1)

    def _wire_pages(self):
        self.dashboard.startRequested.connect(self.start_engine)
        self.dashboard.stopRequested.connect(self.stop_engine)
        self.screen_page.valueChanged.connect(self._setting_changed)
        self.detection_page.valueChanged.connect(self._setting_changed)
        self.response_page.valueChanged.connect(self._setting_changed)
        self.controller_page.valueChanged.connect(self._setting_changed)
        self.preferences_page.valueChanged.connect(self._setting_changed)
        self.preferences_page.resetRequested.connect(lambda: self._load_profile("Default"))
        self.response_page.presetSelected.connect(self._apply_preset)
        self.profiles_page.loadRequested.connect(self._load_profile)
        self.profiles_page.saveRequested.connect(self._save_profile)
        self.profiles_page.createRequested.connect(self._create_profile)
        self.profiles_page.renameRequested.connect(self._rename_profile)
        self.profiles_page.duplicateRequested.connect(self._duplicate_profile)
        self.profiles_page.deleteRequested.connect(self._delete_profile)
        self.profiles_page.selected.connect(lambda _: self.profiles_page.set_active(self.current_profile))
        self.diagnostics_page.copyRequested.connect(self._copy_diagnostics)
        self.diagnostics_page.openLogsRequested.connect(self._open_log_folder)
        self.diagnostics_page.openDataRequested.connect(self._open_data_folder)
        self.diagnostics_page.openHidHideRequested.connect(self._open_hidhide)
        self.diagnostics_page.clearLogRequested.connect(self._clear_log)
        self.diagnostics_page.repairRequested.connect(self._repair_drivers)

    def _restore_geometry(self):
        if not self.preferences.get("remember_window_position"):
            return
        encoded = self.preferences.get("window_geometry")
        if isinstance(encoded, str) and encoded:
            try:
                self.restoreGeometry(QByteArray.fromBase64(encoded.encode("ascii")))
            except Exception:
                pass

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(self._icon, self)
        menu = QMenu()
        open_action = QAction("Open Panda", self)
        open_action.triggered.connect(self._show_from_tray)
        engine_action = QAction("Start / stop engine", self)
        engine_action.triggered.connect(self._toggle_engine)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self._exit_from_tray)
        menu.addAction(open_action)
        menu.addAction(engine_action)
        menu.addSeparator()
        menu.addAction(exit_action)
        tray.setContextMenu(menu)
        tray.setToolTip("Panda Training Standalone")
        tray.activated.connect(self._tray_activated)
        tray.show()
        self._tray = tray

    def _apply_theme(self):
        accent = str(self.preferences.get("accent_color", "#C7F36B"))
        dark = bool(self.preferences.get("dark_mode", True))
        QApplication.instance().setStyleSheet(stylesheet(dark, accent))
        pixmap = app_icon(accent)
        self._icon = QIcon(pixmap)
        self.setWindowIcon(self._icon)
        if self._tray:
            self._tray.setIcon(self._icon)

    def show_page(self, key: str):
        if key not in self.pages:
            return
        self.stack.setCurrentWidget(self.pages[key])
        title, description = PAGE_META[key]
        self.page_title.setText(title)
        self.page_description.setText(description)
        for name, button in self.nav_buttons.items():
            button.setChecked(name == key)

    def _sync_settings(self):
        self.screen_page.set_values(self.engine_settings)
        self.detection_page.set_values(self.engine_settings)
        self.response_page.set_values(self.engine_settings)
        self.preferences_page.set_values(self.preferences)
        self.controller_page.set_slot_value(self.engine_settings["slot"])
        self.profiles_page.set_active(self.current_profile)

    def _setting_changed(self, key: str, value):
        if key in UI_DEFAULTS:
            old = self.preferences.get(key)
            self.preferences[key] = value
            if key == "launch_on_startup":
                try:
                    set_launch_on_startup(bool(value))
                except Exception as exc:
                    self.preferences[key] = old
                    self.preferences_page.set_values(self.preferences)
                    QMessageBox.warning(self, "Windows startup", str(exc))
                    return
            if key == "minimize_to_tray" and value and self._tray is None:
                self.preferences[key] = False
                self.preferences_page.set_values(self.preferences)
                QMessageBox.information(self, "System tray unavailable", "Windows did not report an available notification area.")
                return
            if key in {"dark_mode", "accent_color"}:
                self._apply_theme()
        else:
            self.engine_settings[key] = value
            if key == "smooth":
                self.engine_settings["horizontal_smooth"] = value
                self.engine_settings["vertical_smooth"] = value
            self.engine_settings = normalize_settings(self.engine_settings)
            self.screen_page.set_values(self.engine_settings)
            self.detection_page.set_values(self.engine_settings)
            self.response_page.set_values(self.engine_settings)
            if self.worker and self.worker.is_alive():
                self.worker.update(self.engine_settings)
            if key in {"preview_enabled", "capture_monitor"} and (key == "capture_monitor" or not value):
                self.screen_page.clear_frame()
                self._last_preview_identity = None
        self.settings = {**self.engine_settings, **self.preferences}
        self._save_timer.start(450)

    def _persist(self):
        try:
            self.profile_store.save(self.current_profile, self.engine_settings)
            self.preferences["last_profile"] = self.current_profile
            self.config_store.save({**self.engine_settings, **self.preferences})
        except Exception as exc:
            self.statusBar().showMessage(f"Settings could not be saved: {exc}", 8000)
            self._log(f"Settings save error: {exc}")

    def _apply_preset(self, name: str):
        try:
            self.engine_settings = apply_response_preset(self.engine_settings, name)
            self._sync_settings()
            if self.worker and self.worker.is_alive():
                self.worker.update(self.engine_settings)
            self._persist()
            self._log(f"Response preset applied: {name}")
            self.statusBar().showMessage(f"{name} response preset applied", 4000)
        except Exception as exc:
            QMessageBox.warning(self, "Preset", str(exc))

    def _refresh_profile_list(self, selected: str | None = None):
        self.profiles_page.set_profiles(self.profile_store.list(), selected or self.current_profile)
        self.profiles_page.set_active(self.current_profile)

    def _load_profile(self, name: str):
        try:
            self.engine_settings = self.profile_store.load(name)
            self.current_profile = name
            self.preferences["last_profile"] = name
            self.settings = {**self.engine_settings, **self.preferences}
            self._sync_settings()
            self._refresh_profile_list(name)
            if self.worker and self.worker.is_alive():
                self.worker.update(self.engine_settings)
            self._persist()
            self._log(f"Profile loaded: {name}")
            self.statusBar().showMessage(f"Loaded profile · {name}", 4000)
        except Exception as exc:
            QMessageBox.warning(self, "Load profile", str(exc))

    def _save_profile(self, name: str):
        if not name:
            return
        try:
            self.profile_store.save(name, self.engine_settings)
            self.preferences["last_profile"] = self.current_profile
            self.config_store.save({**self.engine_settings, **self.preferences})
            self._log(f"Profile saved: {name}")
            self.statusBar().showMessage(f"Saved profile · {name}", 4000)
        except Exception as exc:
            QMessageBox.warning(self, "Save profile", str(exc))

    def _create_profile(self):
        name, accepted = QInputDialog.getText(self, "Create profile", "Profile name:", text="Custom 2")
        if not accepted:
            return
        try:
            self.profile_store.create(name.strip(), self.engine_settings)
            self.current_profile = name.strip()
            self.preferences["last_profile"] = self.current_profile
            self._refresh_profile_list(self.current_profile)
            self._persist()
            self._log(f"Profile created: {self.current_profile}")
        except Exception as exc:
            QMessageBox.warning(self, "Create profile", str(exc))

    def _rename_profile(self, old_name: str):
        if old_name.casefold() == "default":
            QMessageBox.information(self, "Default profile", "The Default profile is kept as the recovery profile.")
            return
        new_name, accepted = QInputDialog.getText(self, "Rename profile", "New profile name:", text=old_name)
        if not accepted:
            return
        try:
            self.profile_store.rename(old_name, new_name.strip())
            if self.current_profile.casefold() == old_name.casefold():
                self.current_profile = new_name.strip()
                self.preferences["last_profile"] = self.current_profile
            self._refresh_profile_list(new_name.strip())
            self._persist()
            self._log(f"Profile renamed: {old_name} → {new_name.strip()}")
        except Exception as exc:
            QMessageBox.warning(self, "Rename profile", str(exc))

    def _duplicate_profile(self, source: str):
        name, accepted = QInputDialog.getText(self, "Duplicate profile", "Copy name:", text=f"{source} Copy")
        if not accepted:
            return
        try:
            self.profile_store.duplicate(source, name.strip())
            self._refresh_profile_list(name.strip())
            self._log(f"Profile duplicated: {source} → {name.strip()}")
        except Exception as exc:
            QMessageBox.warning(self, "Duplicate profile", str(exc))

    def _delete_profile(self, name: str):
        if name.casefold() == "default":
            QMessageBox.information(self, "Default profile", "The Default profile is kept as the recovery profile.")
            return
        answer = QMessageBox.question(self, "Delete profile", f"Delete '{name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.profile_store.delete(name)
            if self.current_profile.casefold() == name.casefold():
                self._load_profile("Default")
            else:
                self._refresh_profile_list()
            self._log(f"Profile deleted: {name}")
        except Exception as exc:
            QMessageBox.warning(self, "Delete profile", str(exc))

    def start_engine(self):
        if self.worker and self.worker.is_alive():
            return
        if not driver_status()["vigem"]:
            self.show_page("diagnostics")
            self.statusBar().showMessage("ViGEmBus is missing. Install it from Diagnostics before starting the engine.", 10000)
            return
        self._persist()
        self.worker = EngineWorker(self.engine_settings, self.events)
        self.worker.start()
        self.dashboard.set_engine_status("Starting engine…")
        self.dashboard.start_button.setEnabled(False)
        self.dashboard.stop_button.setEnabled(True)

    def stop_engine(self):
        if self.worker and self.worker.is_alive():
            self.worker.stop()
            self.dashboard.set_engine_status("Stopping…")
            self.dashboard.start_button.setEnabled(False)
            self.dashboard.stop_button.setEnabled(False)

    def _toggle_engine(self):
        if self.worker and self.worker.is_alive():
            self.stop_engine()
        else:
            self.start_engine()

    def _poll_events(self):
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "status":
                self.dashboard.set_engine_status(payload)
                self.statusBar().showMessage(payload)
            elif kind == "telemetry":
                self.runtime = payload
                self.dashboard.set_telemetry(payload)
                self.controller_page.set_telemetry(payload)
                self.diagnostics_page.set_snapshot(self.system, payload)
                if payload.get("running") is False:
                    self.dashboard.start_button.setEnabled(True)
                    self.dashboard.stop_button.setEnabled(False)
            elif kind in {"log", "warning", "capture_error"}:
                self._log(str(payload))
            elif kind == "fatal":
                self.statusBar().showMessage(str(payload), 10000)
                self.dashboard.set_engine_status("Error · see Diagnostics")
                if self.worker and not self.worker.is_alive():
                    self.dashboard.start_button.setEnabled(True)
                    self.dashboard.stop_button.setEnabled(False)
            elif kind == "driver_setup_started":
                self.statusBar().showMessage("Downloading and launching driver installers…")
            elif kind == "driver_setup_done":
                self._refresh_system()
                QMessageBox.information(self, "Driver setup", str(payload))
            elif kind == "driver_setup_error":
                self._log(f"Driver setup error: {payload}")
                QMessageBox.warning(self, "Driver setup", str(payload))
        self._refresh_live_preview()
        if self._exit_requested and self.worker and not self.worker.is_alive():
            self._allow_close = True
            self.close()

    def _refresh_live_preview(self):
        if self.stack.currentWidget() is not self.screen_page or not self.worker or not self.worker.is_alive():
            return
        preview = self.worker.latest_preview()
        if preview is None:
            return
        identity = id(preview[0])
        if identity != self._last_preview_identity:
            self.screen_page.set_frame(*preview)
            self._last_preview_identity = identity

    def _refresh_system(self):
        self.system = system_snapshot(self.engine_settings["slot"])
        self.dashboard.set_system(self.system)
        if not self.runtime.get("running"):
            self.controller_page.set_telemetry({
                "controller_connected": self.system.get("controller_connected", False),
                "controller_name": self.system.get("controller_name", "Not connected"),
                "slot": self.system.get("xinput_slot"),
                "virtual_controller": "Offline",
            })
        self.diagnostics_page.set_snapshot(self.system, self.runtime)
        installed = self.system.get("vigem_installed")
        self.header_status.set_state("SYSTEM READY" if installed else "DRIVER MISSING")

    def _log(self, message: str):
        self.log_store.write(message)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.diagnostics_page.append_log(f"[{timestamp}] {message}")

    def _repair_drivers(self):
        if self._driver_thread and self._driver_thread.is_alive():
            return
        self.events.put(("driver_setup_started", None))

        def run():
            try:
                result = install_or_repair_drivers()
                self.events.put(("driver_setup_done", result))
            except Exception as exc:
                self.events.put(("driver_setup_error", str(exc)))

        self._driver_thread = threading.Thread(target=run, name="PandaDriverSetup", daemon=True)
        self._driver_thread.start()

    def _copy_diagnostics(self):
        QApplication.clipboard().setText(format_diagnostics(self.system, self.runtime) + "\n\n" + self.log_store.read())
        self.statusBar().showMessage("Diagnostics copied to clipboard", 3500)

    def _open_log_folder(self):
        path = self.config_store.root / "logs"
        path.mkdir(parents=True, exist_ok=True)
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_data_folder(self):
        self.config_store.root.mkdir(parents=True, exist_ok=True)
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.config_store.root)))

    def _open_hidhide(self):
        if not open_hidhide_client():
            QMessageBox.information(self, "HidHide", "HidHide is optional and its control client was not found.")

    def _clear_log(self):
        self.log_store.clear()
        self.diagnostics_page.set_log("")

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_from_tray()

    def _exit_from_tray(self):
        self._exit_requested = True
        if self.worker and self.worker.is_alive():
            self.stop_engine()
            return
        self._allow_close = True
        self.close()

    def closeEvent(self, event):
        if self.preferences.get("minimize_to_tray") and self._tray and not self._exit_requested and not self._allow_close:
            self._save_window_geometry()
            self._persist()
            self.hide()
            event.ignore()
            return
        if self.worker and self.worker.is_alive() and not self._allow_close:
            self.worker.stop()
            self.setEnabled(False)
            event.ignore()
            QTimer.singleShot(60, self._finish_close_when_stopped)
            return
        self._save_window_geometry()
        self._persist()
        if self._tray:
            self._tray.hide()
        event.accept()

    def _finish_close_when_stopped(self):
        if self.worker and self.worker.is_alive():
            QTimer.singleShot(60, self._finish_close_when_stopped)
            return
        self._allow_close = True
        self.setEnabled(True)
        self.close()

    def _save_window_geometry(self):
        if self.preferences.get("remember_window_position") and not self.isMinimized():
            self.preferences["window_geometry"] = bytes(self.saveGeometry().toBase64()).decode("ascii")


def create_application(argv: list[str] | None = None) -> QApplication:
    app = QApplication(argv or sys.argv)
    app.setApplicationName("Panda Training Standalone")
    app.setOrganizationName("Panda")
    app.setQuitOnLastWindowClosed(True)
    app.setStyle("Fusion")
    return app
