from PySide6.QtGui import QColor


def stylesheet(dark: bool = True, accent: str = "#C7F36B") -> str:
    color = QColor(accent)
    if not color.isValid():
        accent = "#C7F36B"
    if dark:
        bg, side, card, raised, border = "#0C0E10", "#111315", "#15181B", "#1B1F22", "#292D31"
        text, muted, input_bg = "#F0F2EF", "#929A9A", "#101214"
    else:
        bg, side, card, raised, border = "#F4F6F4", "#FFFFFF", "#FFFFFF", "#EDF0EC", "#DCE1DC"
        text, muted, input_bg = "#202522", "#68716A", "#F7F8F6"
    return f"""
    QWidget {{ background: transparent; color: {text}; font-family: 'Segoe UI'; font-size: 13px; }}
    QMainWindow {{ background: {bg}; }}
    QFrame#sidebar {{ background: {side}; border-right: 1px solid {border}; }}
    QFrame#card {{ background: {card}; border: 1px solid {border}; border-radius: 12px; }}
    QFrame#divider {{ background: {border}; border: 0; max-height: 1px; }}
    QLabel#muted {{ color: {muted}; }}
    QLabel#eyebrow {{ color: {muted}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
    QLabel#pageTitle {{ font-size: 25px; font-weight: 700; }}
    QLabel#cardTitle {{ font-size: 14px; font-weight: 650; }}
    QLabel#brand {{ font-size: 19px; font-weight: 800; letter-spacing: 2px; }}
    QPushButton {{ background: {raised}; border: 1px solid {border}; border-radius: 8px; padding: 8px 12px; font-weight: 600; }}
    QPushButton:hover {{ background: {border}; }}
    QPushButton:disabled {{ color: {muted}; background: {card}; }}
    QPushButton#primaryButton {{ background: {accent}; color: #11150B; border: 0; font-size: 14px; font-weight: 800; padding: 12px 20px; }}
    QPushButton#primaryButton:hover {{ background: {accent}; border: 1px solid #FFFFFF; }}
    QPushButton#dangerButton {{ background: #3A2022; color: #FFB7B7; border: 1px solid #654143; }}
    QPushButton#navButton {{ text-align: left; background: transparent; border: 0; padding: 10px 12px; color: {muted}; font-weight: 600; }}
    QPushButton#navButton:hover {{ background: {raised}; color: {text}; }}
    QPushButton#navButton:checked {{ background: {raised}; color: {accent}; border-left: 3px solid {accent}; }}
    QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{ background: {input_bg}; border: 1px solid {border}; border-radius: 7px; padding: 7px 9px; min-height: 22px; selection-background-color: {accent}; }}
    QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{ border-color: {accent}; }}
    QComboBox QAbstractItemView {{ background: {card}; border: 1px solid {border}; selection-background-color: {raised}; }}
    QCheckBox {{ spacing: 9px; }}
    QCheckBox::indicator {{ width: 34px; height: 18px; border-radius: 9px; background: {border}; }}
    QCheckBox::indicator:checked {{ background: {accent}; }}
    QSlider::groove:horizontal {{ height: 4px; background: {border}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {accent}; width: 13px; margin: -5px 0; border-radius: 7px; }}
    QProgressBar {{ background: {raised}; border: 0; border-radius: 4px; height: 8px; text-align: center; }}
    QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}
    QPlainTextEdit {{ background: {input_bg}; border: 1px solid {border}; border-radius: 8px; padding: 10px; selection-background-color: {accent}; font-family: Consolas; font-size: 12px; }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ border: 0; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {border}; border-radius: 4px; min-height: 28px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QListWidget {{ background: {input_bg}; border: 1px solid {border}; border-radius: 8px; padding: 4px; outline: none; }}
    QListWidget::item {{ padding: 9px; border-radius: 6px; }}
    QListWidget::item:selected {{ background: {raised}; color: {accent}; }}
    """
