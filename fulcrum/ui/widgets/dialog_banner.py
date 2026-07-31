"""An identity banner for prominent dialogs.

The mark that opened the dialog, at the same full presence the header tray
gives it, beside an accent title: the move record wears the glowing app
icon and the provenance page its golden kin, from one builder so the two
stay consistent.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel

from fulcrum.ui import ui_scale

_BANNER_ICON_PX = 40
_TITLE_OBJECT_NAME = "BannerTitle"


def banner_row(icon_path: Path | None, title: str) -> QHBoxLayout:
    """The banner as a layout row: icon (when the asset resolves) + title."""
    row = QHBoxLayout()
    if icon_path is not None:
        badge = QLabel()
        side = ui_scale.px(_BANNER_ICON_PX)
        badge.setPixmap(
            QPixmap(str(icon_path)).scaled(
                side,
                side,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        row.addWidget(badge)
    label = QLabel(title)
    label.setObjectName(_TITLE_OBJECT_NAME)
    row.addWidget(label)
    row.addStretch()
    return row
