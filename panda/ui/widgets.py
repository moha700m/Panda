from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


def make_card(title: str | None = None, subtitle: str | None = None):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(12)
    if title:
        heading = QLabel(title)
        heading.setObjectName("cardTitle")
        layout.addWidget(heading)
    if subtitle:
        note = QLabel(subtitle)
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
    return frame, layout


def add_divider(layout):
    line = QFrame()
    line.setObjectName("divider")
    layout.addWidget(line)
    return line


class StatusBadge(QLabel):
    def __init__(self, text: str = "IDLE"):
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(70)
        self.setStyleSheet("padding: 4px 8px; border-radius: 9px; font-size: 10px; font-weight: 800;")
        self.set_state(text)

    def set_state(self, text: str, tone: str | None = None):
        self.setText(text)
        normalized = (tone or text).casefold()
        words = set(normalized.replace("/", " ").replace("·", " ").split())
        if words & {"ready", "connected", "active", "locked", "installed", "on", "running", "pressed"}:
            bg, fg = "#23321E", "#C7F36B"
        elif words & {"error", "missing", "offline", "failed"} or normalized.startswith("not "):
            bg, fg = "#392326", "#F28E91"
        elif words & {"waiting", "idle", "optional", "stopped", "none", "disabled"}:
            bg, fg = "#2A2D30", "#ADB4B1"
        else:
            bg, fg = "#273037", "#A9D3E6"
        self.setStyleSheet(f"background:{bg};color:{fg};padding:4px 8px;border-radius:9px;font-size:10px;font-weight:800;")


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "—", detail: str = ""):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        self.title = QLabel(title.upper())
        self.title.setObjectName("eyebrow")
        self.value = QLabel(value)
        self.value.setStyleSheet("font-size:22px;font-weight:700;")
        self.detail = QLabel(detail)
        self.detail.setObjectName("muted")
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)

    def set_value(self, value: str, detail: str | None = None):
        self.value.setText(value)
        if detail is not None:
            self.detail.setText(detail)


def app_icon(color: str = "#C7F36B") -> QPixmap:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#171B18"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(3, 3, 58, 58, 16, 16)
    painter.setBrush(QColor(color if QColor(color).isValid() else "#C7F36B"))
    painter.drawRoundedRect(17, 16, 9, 32, 4, 4)
    painter.drawRoundedRect(26, 16, 23, 9, 4, 4)
    painter.drawRoundedRect(26, 28, 18, 8, 4, 4)
    painter.end()
    return pixmap
