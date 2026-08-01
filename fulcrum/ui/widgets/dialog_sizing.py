"""Shared opening-size rule for the app's large dialogs.

The org editor, the move record and the hierarchy guide all open at most
of the app window (or of the screen when parentless); each dialog names
its own fill fractions and this helper owns the one computation.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication


def initial_size(parent, parent_fill: float, screen_fill: float) -> QSize:
    """Most of the parent window's size, or the screen's when parentless."""
    if parent is not None:
        base = parent.window().size()
        return QSize(
            round(base.width() * parent_fill),
            round(base.height() * parent_fill),
        )
    available = QGuiApplication.primaryScreen().availableGeometry().size()
    return QSize(
        round(available.width() * screen_fill),
        round(available.height() * screen_fill),
    )
