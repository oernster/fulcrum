"""Dark theme for Fulcrum: amber for meaning, green and red for state.

The ring model is three states and nothing else: no ring at rest, a green
ring while an enabled control is hovered or focused (green reads as "you can
use this") and a permanent red ring while a control is disabled. Amber is
never a ring; it carries data meaning only (the score, authority encoding,
brand text). The 2px transparent default border keeps rings from shifting the
layout. Each colour is defined once here as a token rather than scattered
hex.
"""

from __future__ import annotations

from PySide6.QtGui import QFontDatabase

from fulcrum.shared.resources import find_data_file
from fulcrum.ui import ui_scale
from fulcrum.ui.theme_palettes import (
    DARK,
    DEFAULT_THEME,
    PALETTES,
    THEME_DARK,
)

_FALLBACK_FONT = "sans-serif"


_BASE_FONT_PT = 14
_HEADING_SCALE = 1.5
_SCORE_SCALE = 2.2
_GLYPH_SCALE = 1.3
_COMPACT_SCALE = 0.92
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


def get_qss(theme: str = DEFAULT_THEME) -> str:
    """The full application stylesheet for a theme (unknown names go dark)."""
    p = PALETTES.get(theme, DARK)
    base_pt = round(_BASE_FONT_PT * ui_scale.factor())
    heading_pt = round(base_pt * _HEADING_SCALE)
    score_pt = round(base_pt * _SCORE_SCALE)
    glyph_pt = round(base_pt * _GLYPH_SCALE)
    compact_pt = round(base_pt * _COMPACT_SCALE)
    font_family = _ui_font_family()
    up_arrow = _arrow_image(_SPIN_UP_FILE)
    down_arrow = _arrow_image(_SPIN_DOWN_FILE)
    return f"""
QWidget {{
    background-color: {p.bg};
    color: {p.text};
    font-family: '{font_family}', {_FALLBACK_FONT};
    font-size: {base_pt}pt;
}}
QMainWindow, QDialog {{ background-color: {p.bg}; }}
QLabel {{ background: transparent; color: {p.text}; }}
QLabel#Muted {{ color: {p.text_muted}; }}
QLabel#Heading {{ font-size: {heading_pt}pt; font-weight: 600; }}
QLabel#ScoreValue {{
    font-size: {score_pt}pt; font-weight: 600; color: {p.accent_bright};
}}

QPushButton {{
    background-color: {p.surface_raised};
    color: {p.text};
    border: 2px solid transparent;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton:enabled:hover {{ border-color: {p.ring_green}; }}
/* The centred glow pair (app icon and its provenance kin) sits on a tight
   plate so the marks read large; padding only, so the generic hover and
   focus ring rules still apply. */
QPushButton#TrayGlow {{ padding: 2px 6px; }}
/* The complete picture is a keyboard stop (Enter asks for the drill map),
   so its focus is visible: the standard green ring, transparent at rest so
   gaining focus never reflows the canvas. */
QGraphicsView#CompleteMap {{ border: 2px solid transparent; }}
QGraphicsView#CompleteMap:enabled:focus {{ border: 2px solid {p.ring_green}; }}
QPushButton:enabled:focus {{ border-color: {p.ring_green}; outline: none; }}
QPushButton:pressed {{ background-color: {p.surface}; }}
/* Any button carrying a dropdown menu shares the spinbox arrow, so every
   disclosure cue in the app is the same glyph. */
QPushButton::menu-indicator {{
    image: {down_arrow};
    width: 12px;
    height: 8px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
    right: 6px;
}}
QPushButton:disabled {{
    color: {p.disabled_text};
    background-color: {p.surface};
    border-color: {p.ring_red};
}}
QPushButton#MoveButton {{
    text-align: left;
    padding: 6px 12px;
    font-size: {compact_pt}pt;
}}
QPushButton#SignalChip {{ padding: 6px 10px; font-size: {compact_pt}pt; }}
/* The move record's position arrows: emoji glyphs on a compact chip. */
QPushButton#RecordArrow {{ padding: 6px 12px; font-size: {glyph_pt}pt; }}
/* The record's identity banner: the accent title beside the glowing mark. */
QLabel#RecordTitle {{
    font-size: {score_pt}pt; font-weight: 700; color: {p.accent_bright};
}}
QPushButton#TreeAction, QPushButton#MapZoom {{
    padding: 0;
    min-width: 0;
    font-weight: 700;
    font-size: {glyph_pt}pt;
    border-radius: 6px;
}}
/* The tree's action cells sit over the tree surface; without this they paint
   the window background as opaque blocks in each row. */
QWidget#TreeActionCell {{ background: transparent; }}
QPushButton#IconLink {{
    background: transparent;
    border: 2px solid transparent;
    padding: 4px 10px;
    font-size: {glyph_pt}pt;
}}
QPushButton#IconLink:enabled:hover {{
    border-color: {p.ring_green};
    color: {p.accent_bright};
}}
QPushButton#IconLink:enabled:focus {{
    border-color: {p.ring_green};
    color: {p.accent_bright};
}}
QPushButton#IconLink:disabled {{ border-color: {p.ring_red}; }}
QPushButton#PreviewButton {{
    background: transparent;
    border: 2px solid transparent;
    padding: 4px 8px;
    font-size: {glyph_pt}pt;
}}
QPushButton#PreviewButton:enabled:hover {{
    border-color: {p.ring_green};
    color: {p.accent_bright};
}}
QPushButton#PreviewButton:enabled:focus {{
    border-color: {p.ring_green};
    color: {p.accent_bright};
}}

QFrame#Card, QFrame#Popover {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 10px;
}}

QMenuBar {{
    background-color: {p.bg};
    color: {p.text};
    border-bottom: 1px solid {p.border};
}}
QMenuBar::item {{
    background: transparent;
    padding: 4px 12px;
    border: 2px solid transparent;
    border-radius: 4px;
}}
QMenuBar::item:selected {{ border: 2px solid {p.ring_green}; color: {p.text}; }}
QMenu {{
    background-color: {p.surface};
    color: {p.text};
    border: 1px solid {p.border};
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
    border: 2px solid {p.ring_green};
    color: {p.text};
    background: transparent;
}}
QMenu::separator {{ height: 1px; background-color: {p.border}; margin: 4px 8px; }}

QTextBrowser {{ background: transparent; border: none; color: {p.text}; }}
QToolTip {{
    background-color: {p.surface_raised};
    color: {p.text};
    border: 1px solid {p.accent};
    padding: 4px 8px;
}}

QTableWidget {{
    background-color: {p.surface};
    gridline-color: {p.border};
    color: {p.text};
    border: 1px solid {p.border};
}}

QTreeWidget {{
    background-color: {p.surface};
    color: {p.text};
    border: 1px solid {p.border};
    border-radius: 6px;
}}
QTreeWidget::item {{ padding: 3px 4px; }}
QTreeWidget::item:selected {{
    background-color: {p.surface_raised};
    color: {p.accent_bright};
}}
/* A visible splitter bar with clear space either side: the margins stay
   transparent inside the handle slot, so pane content never butts against
   the bar itself. */
QSplitter::handle {{ background-color: {p.divider}; border-radius: 2px; }}
QSplitter::handle:horizontal {{ width: 3px; margin: 0 10px; }}
QSplitter::handle:vertical {{ height: 3px; margin: 10px 0; }}

QLabel#BlockedReason {{ color: {p.ring_red}; }}
QPushButton#DiceButton {{ padding: 2px 8px; font-size: {glyph_pt}pt; }}
QHeaderView::section {{
    background-color: {p.bg};
    color: {p.text_muted};
    border: 1px solid {p.border};
    padding: 4px;
}}

QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {{
    background-color: {p.surface_raised};
    color: {p.text};
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 4px 8px;
}}
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus {{
    border: 2px solid {p.ring_green};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid {p.border};
    border-top-right-radius: 4px;
    background-color: {p.surface_raised};
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid {p.border};
    border-bottom-right-radius: 4px;
    background-color: {p.surface_raised};
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {p.border};
}}
QSpinBox::up-button:pressed, QSpinBox::down-button:pressed,
QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {{
    background-color: {p.accent};
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

QCheckBox {{ spacing: 8px; color: {p.text}; background: transparent; }}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {p.text_muted};
    border-radius: 3px;
    background: transparent;
}}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; }}

/* The guide's grow toggle wears the growth accent when on: the same colour
   marks the tree rows whose line growth changes, tying cause to effect. */
QCheckBox#GrowToggle:checked {{ color: {p.growth}; }}
QCheckBox#GrowToggle::indicator:checked {{
    background: {p.growth};
    border-color: {p.growth};
}}

QRadioButton {{ spacing: 8px; color: {p.text}; background: transparent; }}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {p.text_muted};
    border-radius: 10px;
    background: transparent;
}}
QRadioButton::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; }}
QRadioButton::indicator:enabled:hover {{ border-color: {p.ring_green}; }}

QSlider::groove:horizontal {{
    height: 4px; background: {p.border}; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 16px;
    background: {p.accent};
    border-radius: 8px;
    margin: -6px 0;
}}

/* Both scrollbar orientations share the splitter bar's muted colour, so no
   native light strip breaks the theme and every divider-like line matches. */
QScrollBar:vertical {{ background-color: {p.surface}; width: 8px; }}
QScrollBar:horizontal {{ background-color: {p.surface}; height: 8px; }}
QScrollBar::handle:vertical {{
    background-color: {p.divider};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:horizontal {{
    background-color: {p.divider};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QStatusBar {{
    background-color: {p.bg};
    color: {p.text_muted};
    border-top: 1px solid {p.border};
}}
"""


def get_dark_qss() -> str:
    """The dark stylesheet, kept as the historical entry point."""
    return get_qss(THEME_DARK)
