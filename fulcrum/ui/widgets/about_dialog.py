"""About and Licence dialogs for Fulcrum, in the ClearBudget style."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from fulcrum.shared.resources import find_about_png
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog
from fulcrum.version import APP_AUTHOR, APP_NAME, APP_TAGLINE, __version__

_ICON_PX = 96
_DIALOG_MIN_WIDTH = 540
_BODY_MIN_HEIGHT = 320
_LICENCE_MIN_WIDTH = 680
_LICENCE_MIN_HEIGHT = 520

_CREDITS = (
    "<li><b>Python</b> - Python Software Foundation Licence.</li>",
    "<li><b>PySide6 (Qt for Python)</b> - LGPL-3.0.</li>",
    "<li><b>pytest, black, flake8</b> - MIT Licence (development).</li>",
    "<li><b>Pillow</b> - HPND Licence (icon build).</li>",
)

_ABOUT_TEMPLATE = (
    "<h2>{name}</h2>"
    "<p><b>{tagline}</b></p>"
    "<p><b>Version:</b> {version}</p>"
    "<p><b>Author:</b> {author}</p>"
    "<p>Dual-licensed: the model under GPL-3.0 and the user interface under "
    "LGPL-3.0. See the Help menu for both licences.</p>"
    "<hr>"
    "<h3>Open source credits</h3>"
    "<ul>{credits}</ul>"
    "<p>Built on the Python and Qt ecosystems, with thanks to their "
    "communities.</p>"
)

_LICENCE_FALLBACK = "The licence text could not be located in this build."


def _close_row(dialog: QDialog) -> QHBoxLayout:
    row = QHBoxLayout()
    close_button = QPushButton("Close")
    close_button.clicked.connect(dialog.accept)
    row.addStretch()
    row.addWidget(close_button)
    return row


class AboutDialog(NeutralDialog):
    """About Fulcrum: icon, version, author and library credits."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumWidth(ui_scale.px(_DIALOG_MIN_WIDTH))
        layout = QVBoxLayout(self)

        icon_path = find_about_png()
        if icon_path is not None:
            label = QLabel()
            pixmap = QPixmap(str(icon_path)).scaled(
                ui_scale.px(_ICON_PX),
                ui_scale.px(_ICON_PX),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)

        body = QTextBrowser()
        body.setOpenExternalLinks(True)
        body.setHtml(
            _ABOUT_TEMPLATE.format(
                name=APP_NAME,
                tagline=APP_TAGLINE,
                version=__version__,
                author=APP_AUTHOR,
                credits="".join(_CREDITS),
            )
        )
        body.setMinimumHeight(ui_scale.px(_BODY_MIN_HEIGHT))
        layout.addWidget(body)
        layout.addLayout(_close_row(self))


class LicenceDialog(NeutralDialog):
    """Shows a bundled licence text verbatim."""

    def __init__(self, title: str, path: Path | None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(
            ui_scale.px(_LICENCE_MIN_WIDTH), ui_scale.px(_LICENCE_MIN_HEIGHT)
        )
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        browser.setPlainText(_read_licence(path))
        layout.addWidget(browser)
        layout.addLayout(_close_row(self))


def _read_licence(path: Path | None) -> str:
    if path is None:
        return _LICENCE_FALLBACK
    return path.read_text(encoding="utf-8")
