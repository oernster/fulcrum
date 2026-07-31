"""Construction of the main window's header-tray buttons.

The tray holds three kinds of control: icon-only buttons built from the
generated per-theme glyphs (their old text living on as tooltips), the app
icon standing at the centre as the organisation-overview button and the
sun/moon theme toggle. The toggle shows the ACTION a press performs, never
the state: in dark mode it wears the sun (press for light), in light mode
the moon.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton

from fulcrum.shared.resources import find_about_png, find_provenance_png
from fulcrum.ui import ui_scale
from fulcrum.ui.icons import button_icon
from fulcrum.ui.theme_palettes import THEME_DARK

_ICON_LINK = "IconLink"
_TRAY_GLOW = "TrayGlow"
_BUTTON_ICON_PX = 24
# The centred glow pair (the app icon and its golden provenance kin) sits
# larger than the other header buttons, on a tighter plate (see the
# TrayGlow padding rule in theme.py), so the marks read at full presence.
_APP_ICON_PX = 36
_SUN_GLYPH = "\N{BLACK SUN WITH RAYS}\N{VARIATION SELECTOR-16}"
_MOON_GLYPH = "\N{CRESCENT MOON}"
_TO_LIGHT_TOOLTIP = "Switch to light mode"
_TO_DARK_TOOLTIP = "Switch to dark mode"


def icon_button(name: str, tooltip: str, handler, theme: str) -> QPushButton:
    """An icon-only header button whose old text lives on as the tooltip."""
    button = QPushButton()
    button.setIcon(button_icon(name, theme))
    button.setIconSize(
        QSize(ui_scale.px(_BUTTON_ICON_PX), ui_scale.px(_BUTTON_ICON_PX))
    )
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.clicked.connect(handler)
    return button


def _glow_button(icon_path: Path | None, tooltip: str, handler) -> QPushButton:
    """A centred-tray glow button: standard plate, tight padding, large mark.

    Deliberately NOT an icon link: it keeps the standard button plate the
    other header icon buttons have, so the glowing mark sits on the same
    grey square in both themes instead of washing out on a light surface.
    """
    button = QPushButton()
    button.setObjectName(_TRAY_GLOW)
    if icon_path is not None:
        button.setIcon(QIcon(str(icon_path)))
    button.setIconSize(QSize(ui_scale.px(_APP_ICON_PX), ui_scale.px(_APP_ICON_PX)))
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.clicked.connect(handler)
    return button


def app_icon_button(tooltip: str, handler) -> QPushButton:
    """The app icon as a button: sits at the tray's centre, opens the overview."""
    return _glow_button(find_about_png(), tooltip, handler)


def provenance_icon_button(tooltip: str, handler) -> QPushButton:
    """The golden kin of the app icon: opens what grounds the numbers."""
    return _glow_button(find_provenance_png(), tooltip, handler)


def theme_toggle_button(handler) -> QPushButton:
    """The sun/moon theme toggle; dress_theme_toggle sets its face."""
    button = QPushButton()
    button.setObjectName(_ICON_LINK)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.clicked.connect(handler)
    return button


def dress_theme_toggle(button: QPushButton, theme: str) -> None:
    """Show the theme a press switches TO: sun in the dark, moon in the light."""
    dark = theme == THEME_DARK
    button.setText(_SUN_GLYPH if dark else _MOON_GLYPH)
    tooltip = _TO_LIGHT_TOOLTIP if dark else _TO_DARK_TOOLTIP
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
