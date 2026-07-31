"""Loading the generated button icons (assets/buttons) as QIcons.

The PNGs are drawn by generate_button_icons.py at the sizes listed here in
one variant per theme (light strokes for the dark theme, dark strokes with
a _light suffix for the light theme); building a QIcon from every size
keeps buttons crisp at any UI scale.
"""

from __future__ import annotations

from PySide6.QtGui import QIcon

from fulcrum.shared.resources import find_button_icon
from fulcrum.ui.theme_palettes import DEFAULT_THEME, THEME_LIGHT

_BUTTON_ICON_SIZES = (32, 64, 256)
_LIGHT_SUFFIX = "_light"


def button_icon(name: str, theme: str = DEFAULT_THEME) -> QIcon:
    """Build a QIcon from the generated per-size PNGs for a theme."""
    suffix = _LIGHT_SUFFIX if theme == THEME_LIGHT else ""
    icon = QIcon()
    for size in _BUTTON_ICON_SIZES:
        path = find_button_icon(f"{name}{suffix}_{size}.png")
        if path is not None:
            icon.addFile(str(path))
    return icon
