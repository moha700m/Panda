from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QColorDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from panda.core.config import RESPONSE_PRESETS
from panda.ui.widgets import make_card


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str
    description: str = ""
    minimum: float = 0
    maximum: float = 100
    step: float = 1
    scale: int = 1
    choices: tuple[tuple[str, Any], ...] = ()


def slider(key: str, label: str, minimum: float, maximum: float, step: float = 1, scale: int = 1, description: str = "") -> Field:
    return Field(key, label, "slider", description, minimum, maximum, step, scale)


def spin(key: str, label: str, minimum: int, maximum: int, description: str = "") -> Field:
    return Field(key, label, "spin", description, minimum, maximum)


def combo(key: str, label: str, choices: tuple[tuple[str, Any], ...], description: str = "") -> Field:
    return Field(key, label, "combo", description, choices=choices)


def toggle(key: str, label: str, description: str = "") -> Field:
    return Field(key, label, "toggle", description)


class SettingRow(QFrame):
    changed = Signal(str, object)

    def __init__(self, field: Field):
        super().__init__()
        self.field = field
        self.setObjectName("settingRow")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 9, 0, 9)
        row.setSpacing(18)
        labels = QVBoxLayout()
        labels.setSpacing(3)
        title = QLabel(field.label)
        title.setStyleSheet("font-weight:600;")
        labels.addWidget(title)
        if field.description:
            note = QLabel(field.description)
            note.setObjectName("muted")
            note.setWordWrap(True)
            labels.addWidget(note)
        row.addLayout(labels, 1)
        self.control = self._create_control()
        row.addWidget(self.control, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setStyleSheet("QFrame#settingRow { border-bottom: 1px solid rgba(128, 138, 136, 0.13); }")

    def _create_control(self) -> QWidget:
        field = self.field
        if field.kind == "combo":
            control = QComboBox()
            for label, value in field.choices:
                control.addItem(label, value)
            control.setMinimumWidth(170)
            control.currentIndexChanged.connect(lambda: self.changed.emit(field.key, control.currentData()))
            return control
        if field.kind == "toggle":
            control = QCheckBox()
            control.stateChanged.connect(lambda state: self.changed.emit(field.key, state == Qt.CheckState.Checked.value))
            return control
        if field.kind == "spin":
            control = QSpinBox()
            control.setRange(int(field.minimum), int(field.maximum))
            control.setFixedWidth(112)
            control.valueChanged.connect(lambda value: self.changed.emit(field.key, value))
            return control
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        control = QSlider(Qt.Orientation.Horizontal)
        control.setMinimumWidth(175)
        control.setRange(int(field.minimum * field.scale), int(field.maximum * field.scale))
        control.setSingleStep(max(1, int(field.step * field.scale)))
        value = QLabel()
        value.setMinimumWidth(58)
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        def update(position: int):
            if field.key == "kernel" and position % 2 == 0:
                corrected = position + 1 if position < int(field.maximum * field.scale) else position - 1
                blocker = QSignalBlocker(control)
                control.setValue(corrected)
                del blocker
                position = corrected
            actual = position / field.scale
            if field.scale == 1:
                value.setText(str(int(actual)))
                output: Any = int(actual)
            else:
                value.setText(f"{actual:.2f}".rstrip("0").rstrip("."))
                output = float(actual)
            self.changed.emit(field.key, output)

        control.valueChanged.connect(update)
        self.slider_value = value
        layout.addWidget(control, 1)
        layout.addWidget(value)
        self.slider = control
        return container

    def set_value(self, value: Any):
        field = self.field
        if field.kind == "combo":
            blocker = QSignalBlocker(self.control)
            index = self.control.findData(value)
            self.control.setCurrentIndex(max(0, index))
            del blocker
        elif field.kind == "toggle":
            blocker = QSignalBlocker(self.control)
            self.control.setChecked(bool(value))
            del blocker
        elif field.kind == "spin":
            blocker = QSignalBlocker(self.control)
            self.control.setValue(int(value))
            del blocker
        else:
            position = round(float(value) * field.scale)
            blocker = QSignalBlocker(self.slider)
            self.slider.setValue(position)
            del blocker
            if field.scale == 1:
                self.slider_value.setText(str(int(value)))
            else:
                self.slider_value.setText(f"{float(value):.2f}".rstrip("0").rstrip("."))


class SettingPage(QWidget):
    valueChanged = Signal(str, object)
    presetSelected = Signal(str)

    def __init__(self, heading: str, description: str, sections: tuple[tuple[str, tuple[Field, ...]], ...]):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 2, 12, 20)
        body_layout.setSpacing(14)
        title = QLabel(heading)
        title.setObjectName("cardTitle")
        note = QLabel(description)
        note.setObjectName("muted")
        note.setWordWrap(True)
        body_layout.addWidget(title)
        body_layout.addWidget(note)
        self.rows: dict[str, SettingRow] = {}
        self.section_frames: dict[str, QFrame] = {}
        for title_text, fields in sections:
            frame, layout = make_card(title_text)
            self.section_frames[title_text] = frame
            for field in fields:
                row = SettingRow(field)
                row.changed.connect(self.valueChanged)
                self.rows[field.key] = row
                layout.addWidget(row)
            body_layout.addWidget(frame)
        body_layout.addStretch(1)
        scroll.setWidget(body)

    def set_values(self, values: dict[str, Any]):
        for key, row in self.rows.items():
            if key in values:
                row.set_value(values[key])
        if "target_color" in values and "Custom HSV range" in self.section_frames:
            self.set_section_visible("Custom HSV range", values["target_color"] == "custom")

    def set_section_visible(self, title: str, visible: bool):
        frame = self.section_frames.get(title)
        if frame:
            frame.setVisible(visible)


class ImagePreview(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(225)
        self.setMaximumHeight(320)
        self._pixmap: QPixmap | None = None
        self._frame_size = (0, 0)
        self._point: tuple[float, float] | None = None
        self._box: tuple[int, int, int, int] | None = None
        self.fov = 170
        self.show_fov = True
        self.show_marker = True
        self.opacity = 0.75

    def set_frame(self, frame: np.ndarray, point=None, box=None):
        if frame.ndim != 3 or frame.shape[2] < 3:
            return
        height, width = frame.shape[:2]
        image = QImage(frame.data, width, height, int(frame.strides[0]), QImage.Format.Format_BGR888).copy()
        self._pixmap = QPixmap.fromImage(image)
        self._frame_size = (width, height)
        self._point, self._box = point, box
        self.update()

    def set_options(self, fov: int, show_fov: bool, show_marker: bool, opacity: float):
        self.fov = fov
        self.show_fov = show_fov
        self.show_marker = show_marker
        self.opacity = opacity
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#090B0C"))
        target = self.rect().adjusted(8, 8, -8, -8)
        if self._pixmap is None:
            painter.setPen(QColor("#818987"))
            painter.drawText(target, Qt.AlignmentFlag.AlignCenter, "Enable Show Detection Preview to view the selected display")
            painter.end()
            return
        scaled = self._pixmap.scaled(target.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        x = target.x() + (target.width() - scaled.width()) // 2
        y = target.y() + (target.height() - scaled.height()) // 2
        image_rect = scaled.rect().translated(x, y)
        painter.drawPixmap(image_rect, scaled)
        source_width, source_height = self._frame_size
        scale_x, scale_y = scaled.width() / source_width, scaled.height() / source_height
        center_x = x + scaled.width() / 2
        center_y = y + scaled.height() / 2
        painter.setOpacity(self.opacity)
        if self.show_fov:
            radius = int(self.fov * min(scale_x, scale_y))
            painter.setPen(QPen(QColor("#C7F36B"), 1.3, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(int(center_x - radius), int(center_y - radius), radius * 2, radius * 2)
        if self.show_marker:
            painter.setPen(QPen(QColor("#FFFFFF"), 1.4))
            painter.drawLine(int(center_x - 8), int(center_y), int(center_x + 8), int(center_y))
            painter.drawLine(int(center_x), int(center_y - 8), int(center_x), int(center_y + 8))
            if self._point:
                px = x + self._point[0] * scale_x
                py = y + self._point[1] * scale_y
                painter.setPen(QPen(QColor("#C7F36B"), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(int(px - 6), int(py - 6), 12, 12)
        painter.setPen(QPen(QColor("#C7F36B"), 1.5))
        if self._box and self.show_marker:
            left, top, width, height = self._box
            painter.drawRect(int(x + left * scale_x), int(y + top * scale_y), int(width * scale_x), int(height * scale_y))
        painter.setOpacity(1.0)
        painter.end()


class ScreenPage(QWidget):
    valueChanged = Signal(str, object)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        card, card_layout = make_card("Capture preview", "Preview updates on the worker thread and is limited by Preview FPS.")
        self.preview = ImagePreview()
        card_layout.addWidget(self.preview)
        layout.addWidget(card)
        self.settings = SettingPage("Screen capture", "Choose the DXcam display and region used by the vision engine.", (
            ("Capture source", (
                combo("capture_monitor", "Capture monitor", (("Display 1", 0), ("Display 2", 1), ("Display 3", 2))),
                combo("fps", "Capture FPS", tuple((str(value), value) for value in (30, 60, 90, 120, 144, 165, 240))),
                combo("capture_region", "Capture region", (("Center region", "center"), ("Full screen", "full"), ("Custom", "custom"))),
                slider("fov", "FOV radius", 30, 600, description="Detection radius in pixels around screen center."),
            )),
            ("Preview and overlay", (
                toggle("preview_enabled", "Show detection preview", "A low-rate image preview; disabled by default to reduce capture copies."),
                toggle("show_fov", "Show FOV overlay"),
                toggle("show_marker", "Show target marker"),
                slider("overlay_opacity", "Overlay opacity", 0.1, 1.0, 0.05, 100),
                spin("preview_fps", "Preview FPS", 1, 60),
            )),
            ("Custom region size", (
                spin("custom_width", "Width (pixels)", 64, 7680),
                spin("custom_height", "Height (pixels)", 64, 4320),
            )),
        ))
        self.settings.valueChanged.connect(self.valueChanged)
        layout.addWidget(self.settings, 1)

    def set_values(self, values: dict[str, Any]):
        self.settings.set_values(values)
        self.preview.set_options(values.get("fov", 170), values.get("show_fov", True), values.get("show_marker", True), values.get("overlay_opacity", 0.75))

    def set_frame(self, frame, point=None, box=None):
        self.preview.set_frame(frame, point, box)

    def clear_frame(self):
        self.preview._pixmap = None
        self.preview._point = None
        self.preview._box = None
        self.preview.update()

    def update_value(self, key: str, value: Any, all_values: dict[str, Any]):
        if key in self.settings.rows:
            self.settings.set_values({key: value})
        self.preview.set_options(all_values.get("fov", 170), all_values.get("show_fov", True), all_values.get("show_marker", True), all_values.get("overlay_opacity", 0.75))


COLOR_CHOICES = (("Red", "red"), ("Purple", "purple"), ("Yellow", "yellow"), ("Green", "green"), ("Custom HSV", "custom"))


def build_detection_page() -> SettingPage:
    page = SettingPage("Detection", "Tune the color mask, candidate selection, offsets, and target tracking lifetime.", (
        ("Color and filter", (
            combo("target_color", "Target color", COLOR_CHOICES),
            slider("detection_threshold", "Detection threshold", 0, 100),
            spin("min_area", "Minimum target area", 1, 100000),
            spin("max_area", "Maximum target area", 1, 1000000),
            toggle("noise_filter", "Noise filter", "Morphological open removes isolated pixels before selecting a target."),
            slider("kernel", "Kernel size", 1, 31, 2),
        )),
        ("Custom HSV range", (
            spin("hsv_h_min", "Hue minimum (0–179)", 0, 179),
            spin("hsv_h_max", "Hue maximum (0–179)", 0, 179),
            spin("hsv_s_min", "Saturation minimum", 0, 255),
            spin("hsv_s_max", "Saturation maximum", 0, 255),
            spin("hsv_v_min", "Value minimum", 0, 255),
            spin("hsv_v_max", "Value maximum", 0, 255),
        )),
        ("Target selection and offsets", (
            combo("target_selection", "Target selection", (("Closest to crosshair", "closest_to_crosshair"), ("Largest", "largest"), ("Highest confidence", "highest_confidence"))),
            combo("target_anchor", "Target anchor", (("Upper target", "upper"), ("Center mass", "center"))),
            slider("head_offset", "Upper target offset", -1.0, 1.0, 0.01, 100),
            slider("center_mass_offset", "Center mass offset", -1.0, 1.0, 0.01, 100),
            slider("horizontal_offset_px", "Horizontal offset (px)", -200, 200),
            slider("vertical_offset_px", "Vertical offset (px)", -200, 200),
            slider("dead", "Deadzone (pixels)", 0, 200),
            slider("fov", "FOV radius (pixels)", 30, 600),
        )),
        ("Confidence and tracking", (
            slider("conf", "Confidence threshold", 0, 100),
            spin("target_persistence_ms", "Target persistence (ms)", 0, 2000),
            spin("lost_timeout_ms", "Lost-target timeout (ms)", 0, 2000),
            combo("detection_hz", "Detection refresh rate", tuple((f"{value} Hz", value) for value in (15, 30, 60, 90, 120, 144, 165, 240))),
            spin("target_switch_delay_ms", "Target switch delay (ms)", 0, 2000),
        )),
    ))
    page.set_section_visible("Custom HSV range", False)
    return page


def build_response_page() -> SettingPage:
    page = SettingPage("Response", "Adjust right-stick correction response. Left-stick input remains unchanged.", (
        ("Correction", (
            slider("smooth", "Smooth", 0.01, 1.0, 0.01, 100),
            slider("strength", "Strength", 0.01, 1.0, 0.01, 100),
            slider("max_corr", "Maximum correction", 100, 20000),
            slider("x_strength", "X strength", 0.0, 2.0, 0.01, 100),
            slider("y_strength", "Y strength", 0.0, 2.0, 0.01, 100),
            slider("max_x", "Maximum X correction", 100, 32767),
            slider("max_y", "Maximum Y correction", 100, 32767),
            slider("dead", "Deadzone (pixels)", 0, 200),
        )),
        ("Response curve and timing", (
            combo("curve", "Response curve", (("Linear", "linear"), ("Smooth", "smooth"), ("Dynamic", "dynamic"))),
            slider("acceleration", "Acceleration", 0.0, 1.0, 0.01, 100),
            slider("horizontal_smooth", "Horizontal smoothing", 0.01, 1.0, 0.01, 100),
            slider("vertical_smooth", "Vertical smoothing", 0.01, 1.0, 0.01, 100),
            spin("ramp_up_ms", "Ramp-up time (ms)", 0, 2000),
            spin("ramp_down_ms", "Ramp-down time (ms)", 0, 2000),
            spin("correction_delay_ms", "Correction delay (ms)", 0, 2000),
            spin("target_switch_delay_ms", "Target switch delay (ms)", 0, 2000),
        )),
        ("Activation", (
            slider("ads", "ADS activation threshold", 0, 255),
            combo("activation_mode", "Activation mode", (("ADS only", "ads_only"), ("Manual hotkey", "manual_hotkey"), ("Disabled", "disabled"))),
            combo("manual_hotkey", "Manual hotkey", tuple((key, key) for key in ("HOME", "F8", "F9", "F10", "F11", "F12"))),
            toggle("enabled", "Enable screen correction"),
        )),
    ))
    top = QVBoxLayout()
    card, layout = make_card("Quick response preset", "Presets write real response settings and can be adjusted afterward.")
    select = QComboBox()
    select.addItems(RESPONSE_PRESETS.keys())
    button = QPushButton("Apply preset")
    row = QHBoxLayout()
    row.addWidget(select, 1)
    row.addWidget(button)
    layout.addLayout(row)
    button.clicked.connect(lambda: page.presetSelected.emit(select.currentText()))
    page.layout().insertWidget(0, card)
    return page


class PreferencesPage(QWidget):
    valueChanged = Signal(str, object)
    resetRequested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(14)
        self.general = SettingPage("Settings", "Window behavior and profile persistence.", (
            ("General", (
                toggle("start_minimized", "Start minimized"),
                toggle("remember_window_position", "Remember window position"),
                toggle("auto_load_last_profile", "Auto-load last profile"),
                toggle("launch_on_startup", "Launch on Windows startup"),
                toggle("minimize_to_tray", "Minimize to system tray on close"),
            )),
        ))
        self.general.valueChanged.connect(self.valueChanged)
        layout.addWidget(self.general)
        appearance, appearance_layout = make_card("Appearance", "The default palette is a restrained dark interface with one accent color.")
        row = QHBoxLayout()
        row.addWidget(QLabel("Dark mode"), 1)
        self.dark_mode = QCheckBox()
        self.dark_mode.stateChanged.connect(lambda state: self.valueChanged.emit("dark_mode", state == Qt.CheckState.Checked.value))
        row.addWidget(self.dark_mode)
        appearance_layout.addLayout(row)
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Accent color"), 1)
        self.color_button = QPushButton("Choose color")
        self.color_button.clicked.connect(self._choose_color)
        color_row.addWidget(self.color_button)
        appearance_layout.addLayout(color_row)
        layout.addWidget(appearance)

        update_card, update_layout = make_card("Updates", "Update architecture is reserved for a verified release channel.")
        update_status = QLabel("Automatic updates are not enabled in this version.")
        update_status.setObjectName("muted")
        update_layout.addWidget(update_status)
        layout.addWidget(update_card)
        actions, actions_layout = make_card("Recovery", "Load the saved Default profile if an experimental response profile needs to be reset.")
        reset_button = QPushButton("Load Default profile")
        reset_button.clicked.connect(self.resetRequested)
        actions_layout.addWidget(reset_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(actions)
        layout.addStretch(1)
        self._accent = "#C7F36B"

    def _choose_color(self):
        color = QColorDialog.getColor(QColor(self._accent), self, "Choose accent color")
        if color.isValid():
            self.set_accent(color.name())
            self.valueChanged.emit("accent_color", color.name())

    def set_accent(self, value: str):
        color = QColor(value)
        self._accent = color.name() if color.isValid() else "#C7F36B"
        self.color_button.setStyleSheet(f"background:{self._accent};color:#10120D;font-weight:700;border-radius:7px;padding:7px 12px;")

    def set_values(self, values: dict[str, Any]):
        self.general.set_values(values)
        blocker = QSignalBlocker(self.dark_mode)
        self.dark_mode.setChecked(bool(values.get("dark_mode", True)))
        del blocker
        self.set_accent(values.get("accent_color", "#C7F36B"))


class AboutPage(QWidget):
    def __init__(self, version: str, repository: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        card, card_layout = make_card("PANDA", "Training Vision Controller")
        title = QLabel(f"Panda Training Standalone · {version}")
        title.setStyleSheet("font-size:22px;font-weight:750;")
        note = QLabel("Windows desktop application for screen capture diagnostics, controller passthrough, and profile management.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        link = QLabel(f'<a href="{repository}">{repository}</a>')
        link.setOpenExternalLinks(True)
        card_layout.addWidget(title)
        card_layout.addWidget(note)
        card_layout.addWidget(link)
        layout.addWidget(card)
        update_card, update_layout = make_card("Release channel", "The app is packaged as a one-file, windowed Windows executable.")
        update_layout.addWidget(QLabel("Auto-update is disabled; releases are supplied through the repository build artifact."))
        layout.addWidget(update_card)
        layout.addStretch(1)
