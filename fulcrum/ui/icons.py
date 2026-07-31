"""Loading the generated button icons (assets/buttons) as QIcons.

The PNGs are drawn by generate_button_icons.py at the sizes listed here;
building a QIcon from every size keeps buttons crisp at any UI scale.
"""

from __future__ import annotations

from PySide6.QtGui import QIcon

from fulcrum.shared.resources import find_button_icon

_BUTTON_ICON_SIZES = (32, 64, 256)


def button_icon(name: str) -> QIcon:
    """Build a QIcon from the generated per-size header-button PNGs."""
    icon = QIcon()
    for size in _BUTTON_ICON_SIZES:
        path = find_button_icon(f"{name}_{size}.png")
        if path is not None:
            icon.addFile(str(path))
    return icon
