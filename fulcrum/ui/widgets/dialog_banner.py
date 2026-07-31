"""An identity banner for prominent dialogs.

The mark that opened the dialog, at the same full presence the header tray
gives it, beside an accent title: the move record wears the glowing app
icon and the provenance page its golden kin, from one builder so the two
stay consistent.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel

from fulcrum.ui import ui_scale

_BANNER_ICON_PX = 40
_TITLE_OBJECT_NAME = "BannerTitle"
# The icon art carries transparent padding and a soft halo whose tail runs
# to the image edge; only pixels at least this opaque count as the visible
# mark when cropping, so the pixmap's bottom row IS the coloured base.
_INK_ALPHA = 64


def _ink_cropped(image: QImage) -> QImage:
    """The image cropped to its visibly coloured bounds."""
    left, top = image.width(), image.height()
    right = bottom = -1
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() >= _INK_ALPHA:
                left = min(left, x)
                right = max(right, x)
                top = min(top, y)
                bottom = max(bottom, y)
    if right < 0:
        return image
    return image.copy(QRect(left, top, right - left + 1, bottom - top + 1))


def banner_row(icon_path: Path | None, title: str) -> QHBoxLayout:
    """The banner as a layout row: icon (when the asset resolves) + title.

    The icon image is cropped to its visibly coloured bounds, both are
    bottom-aligned and the icon is lifted by the title font's descent, so
    the COLOURED base of the mark (never its transparent padding or halo
    tail) sits on the text baseline.
    """
    row = QHBoxLayout()
    label = QLabel(title)
    label.setObjectName(_TITLE_OBJECT_NAME)
    label.ensurePolished()
    descent = label.fontMetrics().descent()
    if icon_path is not None:
        badge = QLabel()
        side = ui_scale.px(_BANNER_ICON_PX)
        art = _ink_cropped(
            QImage(str(icon_path)).convertToFormat(QImage.Format.Format_ARGB32)
        )
        badge.setPixmap(
            QPixmap.fromImage(art).scaled(
                side,
                side,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        badge.setContentsMargins(0, 0, 0, descent)
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignBottom)
    row.addWidget(label, 0, Qt.AlignmentFlag.AlignBottom)
    row.addStretch()
    return row
