"""Dark theme for Fulcrum, built around an amber interactive accent.

Every button takes an amber border on hover only while it is enabled, never when
disabled; the 2px transparent default border keeps the hover from shifting the
layout. The accent is defined once here as a token rather than scattered hex.
"""

from __future__ import annotations

from PySide6.QtGui import QFontDatabase

from fulcrum.shared.resources import find_data_file
from fulcrum.ui import ui_scale

_FALLBACK_FONT = "sans-serif"

_BG = "#0d0f12"
_SURFACE = "#1a1e24"
_SURFACE_RAISED = "#222831"
_BORDER = "#2c333d"
_TEXT = "#e6e9ee"
_TEXT_MUTED = "#9aa3af"
_ACCENT = "#f59e0b"
_ACCENT_BRIGHT = "#fbbf24"
_DISABLED_TEXT = "#5b6470"

_BASE_FONT_PT = 14
_HEADING_SCALE = 1.5
_SCORE_SCALE = 2.2
_SPIN_UP_FILE = "spin_up.png"
_SPIN_DOWN_FILE = "spin_down.png"


def _ui_font_family() -> str:
    family = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
    return family or _FALLBACK_FONT


def _arrow_image(filename: str) -> str:
    """A QSS image value for a stepper arrow, or 'none' if it is not bundled."""
    path = find_data_file(filename)
    if path is None:
        return "none"
    return f'url("{path.resolve().as_posix()}")'


def get_dark_qss() -> str:
    base_pt = round(_BASE_FONT_PT * ui_scale.factor())
    heading_pt = round(base_pt * _HEADING_SCALE)
    score_pt = round(base_pt * _SCORE_SCALE)
    font_family = _ui_font_family()
    up_arrow = _arrow_image(_SPIN_UP_FILE)
    down_arrow = _arrow_image(_SPIN_DOWN_FILE)
    return f"""
QWidget {{
    background-color: {_BG};
    color: {_TEXT};
    font-family: '{font_family}', {_FALLBACK_FONT};
    font-size: {base_pt}pt;
}}
QMainWindow, QDialog {{ background-color: {_BG}; }}
QLabel {{ background: transparent; color: {_TEXT}; }}
QLabel#Muted {{ color: {_TEXT_MUTED}; }}
QLabel#Heading {{ font-size: {heading_pt}pt; font-weight: 600; }}
QLabel#ScoreValue {{
    font-size: {score_pt}pt; font-weight: 600; color: {_ACCENT_BRIGHT};
}}

QPushButton {{
    background-color: {_SURFACE_RAISED};
    color: {_TEXT};
    border: 2px solid transparent;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton:enabled:hover {{ border-color: {_ACCENT}; }}
QPushButton:enabled:focus {{ border-color: {_ACCENT}; outline: none; }}
QPushButton:pressed {{ background-color: {_SURFACE}; }}
QPushButton:disabled {{ color: {_DISABLED_TEXT}; background-color: {_SURFACE}; }}

QPushButton#Primary {{ background-color: {_ACCENT}; color: {_BG}; }}
QPushButton#Primary:enabled:hover {{ border-color: {_ACCENT_BRIGHT}; }}
QPushButton#MoveButton {{ text-align: left; padding-left: 14px; }}
QPushButton#TreeAction {{ padding: 0; min-width: 0; font-weight: 700; }}

QFrame#Card, QFrame#Popover {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER};
    border-radius: 10px;
}}

QMenuBar {{
    background-color: {_BG};
    color: {_TEXT};
    border-bottom: 1px solid {_BORDER};
}}
QMenuBar::item {{
    background: transparent;
    padding: 4px 12px;
    border: 2px solid transparent;
    border-radius: 4px;
}}
QMenuBar::item:selected {{ border: 2px solid {_ACCENT}; color: {_ACCENT_BRIGHT}; }}
QMenu {{
    background-color: {_SURFACE};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 4px 0;
}}
QMenu::item {{
    padding: 6px 24px;
    border: 2px solid transparent;
    border-radius: 4px;
    margin: 2px 4px;
}}
QMenu::item:selected {{
    border: 2px solid {_ACCENT};
    color: {_ACCENT_BRIGHT};
    background: transparent;
}}
QMenu::separator {{ height: 1px; background-color: {_BORDER}; margin: 4px 8px; }}

QTextBrowser {{ background: transparent; border: none; color: {_TEXT}; }}
QToolTip {{
    background-color: {_SURFACE_RAISED};
    color: {_TEXT};
    border: 1px solid {_ACCENT};
    padding: 4px 8px;
}}

QTableWidget {{
    background-color: {_SURFACE};
    gridline-color: {_BORDER};
    color: {_TEXT};
    border: 1px solid {_BORDER};
}}
QHeaderView::section {{
    background-color: {_BG};
    color: {_TEXT_MUTED};
    border: 1px solid {_BORDER};
    padding: 4px;
}}

QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {{
    background-color: {_SURFACE_RAISED};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
}}
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus {{
    border: 2px solid {_ACCENT};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid {_BORDER};
    border-top-right-radius: 4px;
    background-color: {_SURFACE_RAISED};
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid {_BORDER};
    border-bottom-right-radius: 4px;
    background-color: {_SURFACE_RAISED};
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {_BORDER};
}}
QSpinBox::up-button:pressed, QSpinBox::down-button:pressed,
QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {{
    background-color: {_ACCENT};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: {up_arrow};
    width: 12px;
    height: 8px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: {down_arrow};
    width: 12px;
    height: 8px;
}}

QCheckBox {{ spacing: 8px; color: {_TEXT}; background: transparent; }}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {_TEXT_MUTED};
    border-radius: 3px;
    background: transparent;
}}
QCheckBox::indicator:checked {{ background: {_ACCENT}; border-color: {_ACCENT}; }}

QSlider::groove:horizontal {{ height: 4px; background: {_BORDER}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 16px;
    background: {_ACCENT};
    border-radius: 8px;
    margin: -6px 0;
}}

QScrollBar:vertical {{ background-color: {_SURFACE}; width: 8px; }}
QScrollBar::handle:vertical {{
    background-color: {_BORDER};
    border-radius: 4px;
    min-height: 20px;
}}
QStatusBar {{
    background-color: {_BG};
    color: {_TEXT_MUTED};
    border-top: 1px solid {_BORDER};
}}
"""
