"""Help dialog: the Decision Architecture books behind Fulcrum's model.

Shows the combined hardback as a featured edition above the four series volumes,
each with its cover, a one-line blurb and a link to buy it. The dialog is a
client of the application book showcase and resolves cover images through the
shared resource finder, so it carries no book data of its own.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.books import build_book_showcase
from fulcrum.domain.books import BookEntry
from fulcrum.shared.resources import find_book_cover
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog

_ACCENT = "#f59e0b"
_DIALOG_MIN_WIDTH = 760
_DIALOG_MIN_HEIGHT = 620
_FEATURED_COVER_HEIGHT = 200
_SERIES_COVER_HEIGHT = 150
_SERIES_COLUMNS = 2
_LINK_TEXT = "View on Amazon UK"


def _cover_label(filename: str, height: int) -> QLabel:
    label = QLabel()
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    path = find_book_cover(filename)
    if path is not None:
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            label.setPixmap(
                pixmap.scaledToHeight(
                    ui_scale.px(height),
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
    return label


def _link_label(url: str, align: Qt.AlignmentFlag) -> QLabel:
    label = QLabel(f'<a href="{url}" style="color: {_ACCENT};">{_LINK_TEXT}</a>')
    label.setOpenExternalLinks(True)
    label.setAlignment(align)
    return label


def _heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Heading")
    label.setWordWrap(True)
    return label


def _featured_block(book: BookEntry) -> QFrame:
    frame = QFrame()
    frame.setObjectName("Card")
    row = QHBoxLayout(frame)
    row.addWidget(_cover_label(book.cover_filename, _FEATURED_COVER_HEIGHT))

    text = QVBoxLayout()
    text.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    text.addWidget(_heading(book.title))
    blurb = QLabel(book.blurb)
    blurb.setObjectName("Muted")
    blurb.setWordWrap(True)
    text.addWidget(blurb)
    text.addWidget(_link_label(book.amazon_uk_url, Qt.AlignmentFlag.AlignLeft))
    row.addLayout(text, 1)
    return frame


def _series_card(book: BookEntry) -> QFrame:
    card = QFrame()
    card.setObjectName("Card")
    column = QVBoxLayout(card)
    column.setAlignment(Qt.AlignmentFlag.AlignTop)
    column.addWidget(_cover_label(book.cover_filename, _SERIES_COVER_HEIGHT))

    title = _heading(book.title)
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    column.addWidget(title)

    blurb = QLabel(book.blurb)
    blurb.setObjectName("Muted")
    blurb.setWordWrap(True)
    blurb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    column.addWidget(blurb)

    column.addWidget(_link_label(book.amazon_uk_url, Qt.AlignmentFlag.AlignCenter))
    return card


class BookBackgroundDialog(NeutralDialog):
    """The Decision Architecture books behind Fulcrum, with buy links."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Book background")
        self.setMinimumSize(
            ui_scale.px(_DIALOG_MIN_WIDTH), ui_scale.px(_DIALOG_MIN_HEIGHT)
        )
        showcase = build_book_showcase()

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        content = QVBoxLayout(body)

        content.addWidget(_heading("The Decision Architecture books"))
        intro = QLabel(showcase.intro)
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        content.addWidget(intro)

        content.addWidget(_featured_block(showcase.featured))
        content.addWidget(_heading("The series"))

        grid = QGridLayout()
        for index, book in enumerate(showcase.series):
            grid_row, grid_col = divmod(index, _SERIES_COLUMNS)
            grid.addWidget(_series_card(book), grid_row, grid_col)
        content.addLayout(grid)
        content.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_row.addStretch()
        button_row.addWidget(close_button)
        outer.addLayout(button_row)
