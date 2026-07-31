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
# The icon art carries transparent padding, a soft halo and dim glow skirts
# that read as empty space; a row or column belongs to the visible mark only
# when it holds a substantial run of solidly opaque ink, so the crop's
# bottom row is the mark's PERCEPTUAL base, never a glow tail (the golden
# provenance mark's skirt hung it below the baseline under a laxer rule).
_INK_ALPHA = 128
_MIN_RUN_DIVISOR = 32


def _ink_cropped(image: QImage) -> QImage:
    """The image cropped to its perceptually coloured bounds."""
    width, height = image.width(), image.height()
    strong = [
        [image.pixelColor(x, y).alpha() >= _INK_ALPHA for x in range(width)]
        for y in range(height)
    ]
    min_run = max(1, width // _MIN_RUN_DIVISOR)
    rows = [y for y in range(height) if sum(strong[y]) >= min_run]
    cols = [
        x for x in range(width) if sum(strong[y][x] for y in range(height)) >= min_run
    ]
    if not rows or not cols:
        return image
    return image.copy(
        QRect(cols[0], rows[0], cols[-1] - cols[0] + 1, rows[-1] - rows[0] + 1)
    )


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
