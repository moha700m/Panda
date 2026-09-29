from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from panda.ui.widgets import StatusBadge, make_card


class ControllerPage(QWidget):
    valueChanged = Signal(str, object)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(14)
        card, card_layout = make_card("Controller bridge", "Physical XInput is copied to the virtual Xbox controller; CV output can affect RX and RY only.")
        status_row = QHBoxLayout()
        self.physical = StatusBadge("NOT FOUND")
        self.virtual = StatusBadge("OFFLINE")
        self.slot = QLabel("XInput slot: Auto")
        self.slot.setObjectName("muted")
        self.slot_select = QComboBox()
        for label, value in (("Auto", -1), ("0", 0), ("1", 1), ("2", 2), ("3", 3)):
            self.slot_select.addItem(label, value)
        self.slot_select.currentIndexChanged.connect(lambda: self.valueChanged.emit("slot", self.slot_select.currentData()))
        status_row.addWidget(QLabel("Physical controller"))
        status_row.addWidget(self.physical)
        status_row.addSpacing(18)
        status_row.addWidget(QLabel("Virtual controller"))
        status_row.addWidget(self.virtual)
        status_row.addStretch(1)
        status_row.addWidget(self.slot)
        status_row.addWidget(self.slot_select)
        card_layout.addLayout(status_row)
        layout.addWidget(card)

        inputs, inputs_layout = make_card("Live inputs", "Stick values are shown as a percentage of their range. Triggers are shown from 0 to 100%.")
        self.bars: dict[str, QProgressBar] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(12)
        for index, name in enumerate(("LT", "RT", "LX", "LY", "RX", "RY")):
            row, column = divmod(index, 2)
            label = QLabel(name)
            label.setStyleSheet("font-family:Consolas;font-weight:700;")
            bar = QProgressBar()
            if name in ("LT", "RT"):
                bar.setRange(0, 100)
            else:
                bar.setRange(-100, 100)
            bar.setFormat("%v")
            self.bars[name] = bar
            grid.addWidget(label, row, column * 2)
            grid.addWidget(bar, row, column * 2 + 1)
        inputs_layout.addLayout(grid)
        layout.addWidget(inputs)

        buttons, buttons_layout = make_card("Buttons", "A lit label indicates a currently pressed physical button.")
        self.button_badges: dict[str, StatusBadge] = {}
        button_grid = QGridLayout()
        for index, name in enumerate(("A", "B", "X", "Y", "LB", "RB", "Start", "Back", "D-pad Up", "D-pad Down", "D-pad Left", "D-pad Right", "Left Stick", "Right Stick")):
            badge = StatusBadge(name.upper())
            badge.setMinimumWidth(80)
            self.button_badges[name] = badge
            button_grid.addWidget(badge, index // 5, index % 5)
        buttons_layout.addLayout(button_grid)
        layout.addWidget(buttons)
        layout.addStretch(1)

    def set_telemetry(self, data: dict):
        connected = data.get("controller_connected", False)
        self.physical.set_state("CONNECTED" if connected else "NOT FOUND")
        self.virtual.set_state(data.get("virtual_controller", "Offline").upper())
        slot = data.get("slot")
        self.slot.setText(f"XInput slot: {slot if slot is not None else 'Auto'}")
        values = data.get("inputs", {})
        for key, bar in self.bars.items():
            bar.setValue(int(values.get(key, 0)))
        pressed = data.get("buttons", {})
        for name, badge in self.button_badges.items():
            badge.set_state("PRESSED" if pressed.get(name) else name.upper(), "active" if pressed.get(name) else "idle")

    def set_slot_value(self, slot: int):
        index = self.slot_select.findData(slot)
        self.slot_select.blockSignals(True)
        self.slot_select.setCurrentIndex(max(0, index))
        self.slot_select.blockSignals(False)
