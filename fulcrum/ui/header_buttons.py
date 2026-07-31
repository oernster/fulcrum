"""Construction of the main window's header-tray buttons.

The tray holds three kinds of control: icon-only buttons built from the
generated per-theme glyphs (their old text living on as tooltips), the app
icon standing at the centre as the organisation-overview button and the
sun/moon theme toggle. The toggle shows the ACTION a press performs, never
the state: in dark mode it wears the sun (press for light), in light mode
the moon.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton

from fulcrum.shared.resources import find_about_png
from fulcrum.ui import ui_scale
from fulcrum.ui.icons import button_icon
from fulcrum.ui.theme_palettes import THEME_DARK

_ICON_LINK = "IconLink"
_BUTTON_ICON_PX = 24
_APP_ICON_PX = 28
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


def app_icon_button(tooltip: str, handler) -> QPushButton:
    """The app icon as a button: sits at the tray's centre, opens the overview."""
    button = QPushButton()
    button.setObjectName(_ICON_LINK)
    icon_path = find_about_png()
    if icon_path is not None:
        button.setIcon(QIcon(str(icon_path)))
    button.setIconSize(QSize(ui_scale.px(_APP_ICON_PX), ui_scale.px(_APP_ICON_PX)))
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.clicked.connect(handler)
    return button


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
