"""Help dialog: plain-language definitions of every in-app decision concept.

The content comes from the application glossary (move notes, signal definitions
and the core ideas); a low-key 'Further reading' link points to the books.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from fulcrum.application.glossary import build_glossary
from fulcrum.ui import ui_scale

_MIN_WIDTH = 640
_MIN_HEIGHT = 560
_BOOKS_URL = "https://www.crankthecode.com/books"
_ACCENT = "#f59e0b"
_FURTHER = (
    f'<p><a href="{_BOOKS_URL}" style="color: {_ACCENT};">Further reading: the '
    "Decision Architecture books</a></p>"
)


def _glossary_html() -> str:
    parts = ["<h2>Decision glossary</h2>"]
    for heading, entries in build_glossary():
        parts.append(f"<h3>{heading}</h3>")
        for term, text in entries:
            parts.append(f"<p><b>{term}</b><br>{text}</p>")
    parts.append(_FURTHER)
    return "".join(parts)


class GlossaryDialog(QDialog):
    """Shows the decision glossary with a books 'Further reading' link."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Decision glossary")
        self.setMinimumSize(ui_scale.px(_MIN_WIDTH), ui_scale.px(_MIN_HEIGHT))
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(_glossary_html())
        layout.addWidget(browser)

        row = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        row.addStretch()
        row.addWidget(close_button)
        layout.addLayout(row)
