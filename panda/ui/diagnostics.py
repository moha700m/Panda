from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from panda.ui.widgets import make_card


class DiagnosticsPage(QWidget):
    copyRequested = Signal()
    openLogsRequested = Signal()
    openDataRequested = Signal()
    openHidHideRequested = Signal()
    clearLogRequested = Signal()
    repairRequested = Signal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 12, 0)
        outer.setSpacing(14)
        info, info_layout = make_card("System report", "Hardware checks are read-only and remain available when services or devices are missing.")
        self.values: dict[str, QLabel] = {}
        grid = QGridLayout()
        fields = (
            ("Application version", "application_version"), ("Windows version", "windows_version"),
            ("Screen resolution", "screen_resolution"), ("Monitor count", "monitor_count"),
            ("Capture FPS", "capture_fps"), ("Controller", "controller"),
            ("XInput slot", "xinput_slot"), ("ViGEmBus", "vigem"),
            ("HidHide", "hidhide"), ("Virtual controller", "virtual"),
        )
        for index, (label, key) in enumerate(fields):
            row, column = divmod(index, 2)
            name = QLabel(label)
            name.setObjectName("muted")
            value = QLabel("—")
            value.setStyleSheet("font-weight:600;")
            self.values[key] = value
            grid.addWidget(name, row, column * 2)
            grid.addWidget(value, row, column * 2 + 1)
        info_layout.addLayout(grid)
        outer.addWidget(info)

        log_card, log_layout = make_card("Activity log", "Recent startup, device, capture and engine events.")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(230)
        log_layout.addWidget(self.log)
        row = QHBoxLayout()
        copy = QPushButton("Copy diagnostics")
        open_logs = QPushButton("Open log folder")
        open_data = QPushButton("Open data folder")
        open_hidhide = QPushButton("Open HidHide")
        clear = QPushButton("Clear log")
        repair = QPushButton("Repair drivers")
        copy.clicked.connect(self.copyRequested)
        open_logs.clicked.connect(self.openLogsRequested)
        open_data.clicked.connect(self.openDataRequested)
        open_hidhide.clicked.connect(self.openHidHideRequested)
        clear.clicked.connect(self.clearLogRequested)
        repair.clicked.connect(self.repairRequested)
        for button in (copy, open_logs, open_data, clear, open_hidhide):
            row.addWidget(button)
        row.addStretch(1)
        row.addWidget(repair)
        log_layout.addLayout(row)
        outer.addWidget(log_card, 1)

    def set_snapshot(self, snapshot: dict, runtime: dict):
        self.values["application_version"].setText(str(snapshot.get("application_version", "—")))
        self.values["windows_version"].setText(str(snapshot.get("windows_version", "—")))
        self.values["screen_resolution"].setText(str(snapshot.get("screen_resolution", "—")))
        self.values["monitor_count"].setText(str(snapshot.get("monitor_count", "—")))
        self.values["capture_fps"].setText(f"{runtime.get('capture_fps', 0):.0f} · {runtime.get('capture_status', 'Idle')}")
        live = bool(runtime.get("running"))
        self.values["controller"].setText(str(runtime.get("controller_name") if live else snapshot.get("controller_name", "—")))
        slot = runtime.get("slot") if live else snapshot.get("xinput_slot")
        self.values["xinput_slot"].setText(str(slot if slot is not None else "Auto"))
        vigem = runtime.get("vigem_installed") if runtime.get("running") else snapshot.get("vigem_installed")
        hidhide = runtime.get("hidhide_installed") if runtime.get("running") else snapshot.get("hidhide_installed")
        self.values["vigem"].setText("Installed" if vigem else "Missing")
        self.values["hidhide"].setText("Installed" if hidhide else "Optional / missing")
        self.values["virtual"].setText(str(runtime.get("virtual_controller", "Offline")))

    def set_log(self, contents: str):
        self.log.setPlainText(contents)
        cursor = self.log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log.setTextCursor(cursor)

    def append_log(self, line: str):
        self.log.appendPlainText(line)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
