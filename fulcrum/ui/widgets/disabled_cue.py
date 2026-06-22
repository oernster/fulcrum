"""Disabled-state cues for the move-gated controls.

A disabled QWidget receives no mouse events, so Qt never shows its tooltip; the
help event reaches the first enabled ancestor instead. An application-wide event
filter catches that help event and shows the awaiting-move tooltip for the
disabled control under the cursor. The matching red border lives in theme.py as
QSS keyed to each control's object name.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QPushButton,
    QToolTip,
    QWidget,
)

_AWAITING_MOVE_TIP = "Available once you play a move"
_GATED_PROPERTY = "gated"


class _DisabledTooltip(QObject):
    """Shows the awaiting-move tooltip Qt suppresses for a disabled control."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ToolTip and isinstance(obj, QWidget):
            child = obj.childAt(event.pos())
            if child is not None and not child.isEnabled():
                if child.property(_GATED_PROPERTY):
                    QToolTip.showText(event.globalPos(), _AWAITING_MOVE_TIP)
                    return True
        return super().eventFilter(obj, event)


def install(
    window: QWidget,
    buttons: tuple[QPushButton, ...],
    actions: tuple[QAction, ...],
) -> None:
    """Mark the gated controls and start showing their disabled tooltip."""
    for button in buttons:
        button.setProperty(_GATED_PROPERTY, True)
    for action in actions:
        _gate_action(action)
    QApplication.instance().installEventFilter(_DisabledTooltip(window))


def _gate_action(action: QAction) -> None:
    menu = action.parent()
    if isinstance(menu, QMenu):
        menu.setToolTipsVisible(True)
    action.enabledChanged.connect(
        lambda enabled: action.setToolTip("" if enabled else _AWAITING_MOVE_TIP)
    )
    action.setToolTip("" if action.isEnabled() else _AWAITING_MOVE_TIP)
