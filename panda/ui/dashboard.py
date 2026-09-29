from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from panda.ui.widgets import MetricCard, StatusBadge, add_divider, make_card


class SystemTile(QFrame):
    def __init__(self, label: str):
        super().__init__()
        self.setStyleSheet("QFrame { background: transparent; border: 0; }")
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 3, 2, 3)
        self.label = QLabel(label)
        self.label.setObjectName("muted")
        self.badge = StatusBadge("IDLE")
        row.addWidget(self.label, 1)
        row.addWidget(self.badge)

    def set_state(self, text: str, tone: str | None = None):
        self.badge.set_state(text, tone)


class DashboardPage(QWidget):
    startRequested = Signal()
    stopRequested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(14)

        system, system_layout = make_card("System status", "Live readiness checks for capture and controller services.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(30)
        grid.setVerticalSpacing(4)
        self.tiles = {
            "capture": SystemTile("Screen capture"),
            "controller": SystemTile("Physical controller"),
            "virtual": SystemTile("Virtual controller"),
            "vigem": SystemTile("ViGEmBus"),
            "hidhide": SystemTile("HidHide · optional"),
        }
        for index, tile in enumerate(self.tiles.values()):
            grid.addWidget(tile, index // 2, index % 2)
        system_layout.addLayout(grid)
        layout.addWidget(system)

        engine, engine_layout = make_card("Training engine", "Screen correction is added to the right stick while the selected activation is held.")
        title_row = QHBoxLayout()
        self.engine_state = QLabel("Stopped")
        self.engine_state.setStyleSheet("font-size:17px;font-weight:700;")
        title_row.addWidget(self.engine_state, 1)
        self.start_button = QPushButton("START ENGINE")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self.startRequested)
        self.stop_button = QPushButton("STOP")
        self.stop_button.setObjectName("dangerButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stopRequested)
        title_row.addWidget(self.start_button)
        title_row.addWidget(self.stop_button)
        engine_layout.addLayout(title_row)
        add_divider(engine_layout)
        metric_row = QHBoxLayout()
        metric_row.setSpacing(10)
        self.detection = MetricCard("Detection", "IDLE")
        self.ads = MetricCard("ADS", "OFF")
        self.target = MetricCard("Target", "NONE")
        self.capture_fps = MetricCard("Capture FPS", "0")
        for metric in (self.detection, self.ads, self.target, self.capture_fps):
            metric_row.addWidget(metric, 1)
        engine_layout.addLayout(metric_row)
        data_row = QHBoxLayout()
        confidence_column = QVBoxLayout()
        confidence_label = QLabel("CONFIDENCE")
        confidence_label.setObjectName("eyebrow")
        self.confidence = QProgressBar()
        self.confidence.setRange(0, 100)
        self.confidence.setFormat("%p%")
        confidence_column.addWidget(confidence_label)
        confidence_column.addWidget(self.confidence)
        data_row.addLayout(confidence_column, 1)
        self.correction = QLabel("X: 0     Y: 0")
        self.correction.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.correction.setStyleSheet("font-family:Consolas;font-size:15px;font-weight:700;")
        data_row.addWidget(self.correction, 1)
        engine_layout.addLayout(data_row)
        layout.addWidget(engine)
        note = QLabel("Left stick remains passthrough. The vision engine only adds correction to RX / RY.")
        note.setObjectName("muted")
        layout.addWidget(note)
        layout.addStretch(1)

    def set_system(self, snapshot: dict):
        self.tiles["vigem"].set_state("INSTALLED" if snapshot.get("vigem_installed") else "MISSING")
        self.tiles["hidhide"].set_state("INSTALLED" if snapshot.get("hidhide_installed") else "OPTIONAL")
        connected = snapshot.get("controller_connected", False)
        self.tiles["controller"].set_state("CONNECTED" if connected else "NOT FOUND")

    def set_telemetry(self, data: dict):
        capture = data.get("capture_status", "Idle")
        self.tiles["capture"].set_state({"Ready": "READY", "Error": "ERROR"}.get(capture, "IDLE"))
        self.tiles["controller"].set_state("CONNECTED" if data.get("controller_connected") else "NOT FOUND")
        self.tiles["virtual"].set_state(data.get("virtual_controller", "OFFLINE").upper())
        self.tiles["vigem"].set_state("INSTALLED" if data.get("vigem_installed") else "MISSING")
        self.tiles["hidhide"].set_state("INSTALLED" if data.get("hidhide_installed") else "OPTIONAL")
        running = data.get("running", False)
        self.engine_state.setText("Running" if running else "Stopped")
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.detection.set_value("ACTIVE" if data.get("active") else "IDLE")
        self.ads.set_value("ON" if data.get("ads") else "OFF")
        self.target.set_value("LOCKED" if data.get("target_found") else "NONE", f"{data.get('confidence', 0)}% confidence")
        self.capture_fps.set_value(f"{data.get('capture_fps', 0):.0f}", "frames / second")
        self.confidence.setValue(int(data.get("confidence", 0)))
        self.correction.setText(f"X: {data.get('correction_x', 0):+d}     Y: {data.get('correction_y', 0):+d}")

    def set_engine_status(self, text: str):
        self.engine_state.setText(text)
