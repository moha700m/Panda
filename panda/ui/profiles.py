from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from panda.ui.widgets import make_card


class ProfilesPage(QWidget):
    selected = Signal(str)
    loadRequested = Signal(str)
    saveRequested = Signal(str)
    createRequested = Signal()
    renameRequested = Signal(str)
    duplicateRequested = Signal(str)
    deleteRequested = Signal(str)

    def __init__(self):
        super().__init__()
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 12, 0)
        root.setSpacing(14)
        list_card, list_layout = make_card("Profiles", "Engine settings are stored separately for each profile.")
        self.list = QListWidget()
        self.list.currentTextChanged.connect(self.selected)
        list_layout.addWidget(self.list, 1)
        create = QPushButton("Create profile")
        create.clicked.connect(self.createRequested)
        list_layout.addWidget(create)
        root.addWidget(list_card, 2)

        detail, detail_layout = make_card("Profile actions", "Save updates the selected profile. Load applies its Screen, Detection and Response values immediately.")
        self.active_label = QLabel("Active profile: Default")
        self.active_label.setStyleSheet("font-size:18px;font-weight:700;")
        self.description = QLabel("Select a profile from the list.")
        self.description.setObjectName("muted")
        self.description.setWordWrap(True)
        detail_layout.addWidget(self.active_label)
        detail_layout.addWidget(self.description)
        detail_layout.addStretch(1)
        load = QPushButton("Load profile")
        save = QPushButton("Save current settings")
        row = QHBoxLayout()
        row.addWidget(load)
        row.addWidget(save)
        detail_layout.addLayout(row)
        load.clicked.connect(lambda: self.loadRequested.emit(self.current_name()))
        save.clicked.connect(lambda: self.saveRequested.emit(self.current_name()))
        actions = QHBoxLayout()
        self.rename_button = QPushButton("Rename")
        self.duplicate_button = QPushButton("Duplicate")
        self.delete_button = QPushButton("Delete")
        actions.addWidget(self.rename_button)
        actions.addWidget(self.duplicate_button)
        actions.addWidget(self.delete_button)
        detail_layout.addLayout(actions)
        self.rename_button.clicked.connect(lambda: self.renameRequested.emit(self.current_name()))
        self.duplicate_button.clicked.connect(lambda: self.duplicateRequested.emit(self.current_name()))
        self.delete_button.clicked.connect(lambda: self.deleteRequested.emit(self.current_name()))
        root.addWidget(detail, 3)

    def current_name(self) -> str:
        return self.list.currentItem().text() if self.list.currentItem() else "Default"

    def set_profiles(self, names: list[str], active: str):
        self.list.blockSignals(True)
        self.list.clear()
        self.list.addItems(names)
        items = self.list.findItems(active, Qt.MatchFlag.MatchExactly)
        if items:
            self.list.setCurrentItem(items[0])
        self.list.blockSignals(False)
        self.set_active(active)

    def set_active(self, name: str):
        self.active_label.setText(f"Active profile: {name}")
        current = self.current_name()
        self.description.setText(f"{current} is selected. Load applies it now; Save stores the current settings to this profile.")
        self.delete_button.setEnabled(current.casefold() != "default")
