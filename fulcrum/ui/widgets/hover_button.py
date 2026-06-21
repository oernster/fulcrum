"""A push button that announces hover enter and leave via signals.

Used by the board's signal chips and move buttons so a hover can drive a popover
or a map action without polling, and reused so the behaviour lives in one place.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton


class HoverButton(QPushButton):
    """A QPushButton that emits `entered` on hover-in and `left` on hover-out."""

    entered = Signal()
    left = Signal()

    def enterEvent(self, event) -> None:
        self.entered.emit()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.left.emit()
        super().leaveEvent(event)
