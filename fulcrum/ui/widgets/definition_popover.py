"""A hover popover showing rich text, kept fully on-screen.

The content (a title, an optional gloss and caption/value rows) is supplied by
the caller, so this widget holds no glossary of its own and stays purely in the
UI layer. HoverPopover owns the single live popover: it hides any previous one,
builds a new one, positions it within the screen's available geometry (flipping
above the anchor when there is no room below) then shows it.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from fulcrum.ui import ui_scale

_POPOVER_WIDTH = 320
_ANCHOR_GAP = 6
_SCREEN_MARGIN = 8
_MAX_HEIGHT_FRACTION = 0.7
_FALLBACK_SCREEN_H = 600


def _max_popover_height() -> int:
    """Cap the popover to a fraction of the screen so tall content scrolls."""
    screen = QGuiApplication.primaryScreen()
    height = screen.availableGeometry().height() if screen else _FALLBACK_SCREEN_H
    return int(height * _MAX_HEIGHT_FRACTION)


class Popover(QFrame):
    """Frameless tooltip-style popover with a title, a gloss and detail rows."""

    def __init__(
        self,
        title: str,
        gloss: str,
        rows: tuple[tuple[str, str], ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.ToolTip)
        self.setObjectName("Popover")
        self.setMaximumWidth(ui_scale.px(_POPOVER_WIDTH))

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        inner = QVBoxLayout(content)

        heading = QLabel(title)
        heading.setObjectName("Heading")
        inner.addWidget(heading)

        if gloss:
            body = QLabel(gloss)
            body.setWordWrap(True)
            inner.addWidget(body)

        for caption, value in rows:
            row = QLabel(f"<b>{caption}:</b> {value}")
            row.setWordWrap(True)
            inner.addWidget(row)

        # On a short screen the rows can be taller than the space available, so
        # hold them in a scroll area capped to a fraction of the screen height;
        # the popover then scrolls instead of being clipped off the bottom.
        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMaximumHeight(_max_popover_height())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)


def _on_screen_position(anchor: QWidget, size: QSize) -> QPoint:
    """Place a popover of this size near the anchor, fully within the screen.

    Drops below the anchor when it fits, flips above when the lower edge would
    clip it and clamps inside the available geometry as a last resort. The
    horizontal position is clamped the same way.
    """
    gap = ui_scale.px(_ANCHOR_GAP)
    margin = ui_scale.px(_SCREEN_MARGIN)
    top_left = anchor.mapToGlobal(QPoint(0, 0))
    screen = anchor.screen() or QGuiApplication.primaryScreen()
    available = screen.availableGeometry()

    below = top_left.y() + anchor.height() + gap
    above = top_left.y() - size.height() - gap
    if below + size.height() + margin <= available.bottom():
        top = below
    elif above >= available.top() + margin:
        top = above
    else:
        lowest = available.bottom() - size.height() - margin
        top = max(available.top() + margin, min(below, lowest))

    rightmost = available.right() - size.width() - margin
    left = max(available.left() + margin, min(top_left.x(), rightmost))
    return QPoint(left, top)


class HoverPopover:
    """Owns the one live hover popover: show replaces it, leave hides it."""

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._current: Popover | None = None

    def show(
        self,
        title: str,
        gloss: str,
        rows: tuple[tuple[str, str], ...],
        anchor: QWidget,
    ) -> None:
        self.hide()
        popover = Popover(title, gloss, rows, self._parent)
        popover.adjustSize()
        popover.move(_on_screen_position(anchor, popover.size()))
        popover.show()
        self._current = popover

    def hide(self) -> None:
        if self._current is not None:
            self._current.hide()
            self._current.deleteLater()
            self._current = None
