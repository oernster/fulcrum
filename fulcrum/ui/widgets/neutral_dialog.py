"""A QDialog that opens with neutral focus: nothing is focused until the first Tab.

A zero-size start item holds focus on first show, so no control is pre-selected;
once the first Tab moves focus on to a real control the start item leaves the tab
chain, so the cycle that follows holds only real controls. Subclasses overriding
showEvent must call super().showEvent(event).

Right and Left mirror Tab and Shift+Tab so a dialog is navigable by arrow as well
as Tab. A key event only reaches the dialog once the focused control ignores it,
so a field that needs the horizontal arrows (a line edit, spin box, combo or
radio group) keeps them; only buttons and the like gain arrow navigation.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget


class _NeutralStart(QWidget):
    """An invisible focus holder that leaves the tab chain once focus moves on."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(0, 0)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class NeutralDialog(QDialog):
    """A dialog that opens with no control focused."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._neutral_start = _NeutralStart(self)
        self._neutral_shown = False

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._neutral_shown:
            self._neutral_shown = True
            self._neutral_start.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            self._neutral_start.setFocus(Qt.FocusReason.OtherFocusReason)

    def keyPressEvent(self, event) -> None:
        # Right and Left mirror Tab and Shift+Tab, so a control that reaches here
        # (a button, a checkbox) navigates by arrow too. A field that consumes the
        # horizontal arrows handles them first, so they are never taken from it.
        key = event.key()
        if key == Qt.Key.Key_Right:
            self.focusNextChild()
            event.accept()
            return
        if key == Qt.Key.Key_Left:
            self.focusPreviousChild()
            event.accept()
            return
        super().keyPressEvent(event)
