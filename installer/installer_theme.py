"""The installer's amber theme and its named layout constants.

One stylesheet and one set of geometry tokens, shared by the window and
every dialog, so the installer looks like the application it installs
without importing anything from the ``fulcrum`` package.

British spelling is used in comments. No em dashes appear anywhere.
"""

from __future__ import annotations

import installer_logic as logic

WINDOW_TITLE = f"{logic.APP_DISPLAY_NAME} Installer"

# Window geometry, as named layout constants.
WINDOW_WIDTH = 620
WINDOW_HEIGHT = 560
LICENCE_DIALOG_HEIGHT = 540
LICENCE_FONT_PX = 12
ICON_PX = 56
DIVIDER_PX = 1
BORDER_PX = 1
TEXT_PADDING_PX = 8
SIDES = 2
WIDTH_SAFETY_PX = 8
MARGIN_SIDE = 36
MARGIN_TOP = 28
MARGIN_BOTTOM = 24
DIALOG_MARGIN = 20
SECTION_SPACING = 14
HEADER_SPACING = 14
BUTTON_GAP = 10

# --- Fulcrum amber palette ---------------------------------------------------
# Named colour tokens for the installer surfaces, text and controls. Every
# QPushButton carries a transparent 2px border by default so the green hover
# border does not reflow the layout, and the hover reaction is gated on
# :enabled so disabled buttons stay muted with no border change.
_BACKGROUND = "#0d0f12"
_SURFACE = "#1a1e24"
_SURFACE_RAISED = "#222831"
_BORDER = "#2c333d"
_TEXT = "#e6e9ee"
_TEXT_MUTED = "#9aa3af"
_ACCENT = "#f59e0b"
# Buttons never wear a filled accent: the green hover ring is hard to read
# against an amber or light blue fill, so every button is dark grey with a
# light blue caption and only the ring changes on hover. The amber remains
# on the headings only.
_BUTTON_BLUE = "#7fb0ff"
_DISABLED_TEXT = "#5b6470"
# The app's ring model: no ring at rest, a green ring while an enabled
# control is hovered or focused and a permanent red ring while disabled.
_HOVER_GREEN = "#22c55e"
_DISABLED_BORDER = "#ef4444"

STYLESHEET = f"""
QWidget {{
    background: {_BACKGROUND}; color: {_TEXT}; font-family: 'Segoe UI';
}}
QLabel#HeaderTitle {{
    font-size: 30px; font-weight: 700; color: {_ACCENT};
}}
QLabel#HeaderVersion {{ font-size: 13px; color: {_TEXT_MUTED}; }}
QLabel#SubTitle {{ font-size: 18px; font-weight: 700; color: {_ACCENT}; }}
QLabel#Tagline {{ font-size: 13px; color: {_TEXT_MUTED}; }}
QLabel#InstallPath {{ font-size: 12px; color: {_TEXT_MUTED}; }}
QLabel#StatusLine {{ font-size: 13px; color: {_TEXT}; }}
QFrame#Divider {{ background: {_BORDER}; border: none; }}
QCheckBox {{ spacing: 10px; font-size: 13px; color: {_TEXT}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 2px solid {_TEXT_MUTED};
    border-radius: 3px;
    background: transparent;
}}
QCheckBox::indicator:checked {{
    background: {_ACCENT}; border-color: {_ACCENT};
}}
QPushButton {{
    border: 2px solid transparent;
}}
QPushButton:enabled:hover {{
    border-color: {_HOVER_GREEN};
}}
QPushButton:enabled:focus {{
    border-color: {_HOVER_GREEN}; outline: none;
}}
QPushButton:disabled {{
    border-color: {_DISABLED_BORDER};
}}
QPushButton#LicenceButton {{
    background: {_SURFACE}; color: {_BUTTON_BLUE};
    padding: 8px 16px; border-radius: 16px; font-weight: 600;
}}
QPushButton#PrimaryAction {{
    background: {_SURFACE_RAISED}; color: {_BUTTON_BLUE};
    padding: 12px 28px; border-radius: 22px; font-size: 14px;
    font-weight: 700; min-width: 150px;
}}
QPushButton#PrimaryAction:disabled {{
    background: {_SURFACE_RAISED}; color: {_DISABLED_TEXT};
}}
QPushButton#SecondaryAction {{
    background: {_SURFACE}; color: {_BUTTON_BLUE};
    padding: 12px 22px; border-radius: 22px; font-size: 13px;
    font-weight: 600;
}}
QPushButton#SecondaryAction:disabled {{
    background: {_SURFACE_RAISED}; color: {_DISABLED_TEXT};
}}
QPushButton#DangerAction {{
    background: {_SURFACE_RAISED}; color: {_BUTTON_BLUE};
    padding: 12px 22px; border-radius: 22px; font-size: 13px;
    font-weight: 600;
}}
QPushButton#DangerAction:disabled {{
    background: {_SURFACE_RAISED}; color: {_DISABLED_TEXT};
}}
QTextEdit {{
    background: {_SURFACE}; border: {BORDER_PX}px solid {_BORDER};
    border-radius: 10px; color: {_TEXT}; padding: {TEXT_PADDING_PX}px;
}}
QTextEdit#LicenceView {{
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: {LICENCE_FONT_PX}px;
}}
QDialog {{ background: {_BACKGROUND}; }}
"""
