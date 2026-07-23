"""Leaf widget builders shared by the org editor's tree and inspector panes.

Small, self-contained widget builders holding no editor state, kept here so
the editor modules stay within the structural line limit.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QPushButton

from fulcrum.ui import ui_scale

_HEADING = "Heading"
_TREE_ACTION = "TreeAction"
_ACTION_BUTTON_W = 36
_DICE_GLYPH = "\N{GAME DIE}"
_DICE_TIP = "Roll a different name"


def labelled(label: QLabel) -> QLabel:
    """Tag a label as a heading for the shared stylesheet."""
    label.setObjectName(_HEADING)
    return label


def action_button(glyph: str, tip: str) -> QPushButton:
    """A compact +/- row-action button.

    Only the width is fixed (for column alignment); the height stays the
    stylesheet-computed natural height. Forcing a height below what the
    frame needs makes Qt clip it, which sliced the bottom border off the
    hover ring at some UI scales.
    """
    button = QPushButton(glyph)
    button.setObjectName(_TREE_ACTION)
    button.setToolTip(tip)
    button.setFixedWidth(ui_scale.px(_ACTION_BUTTON_W))
    return button


def dice_button() -> QPushButton:
    """The reroll die shown beside a lead or owner field."""
    button = QPushButton(_DICE_GLYPH)
    button.setObjectName("DiceButton")
    button.setToolTip(_DICE_TIP)
    return button


class ClickOpenComboBox(QComboBox):
    """An editable combo whose whole body opens the list on click.

    An editable combo normally opens only from its arrow; the text area takes
    a click as cursor placement. Here a click anywhere opens the list, as
    every other dropdown in the app does. Typing a custom label still works:
    the click also places the cursor and Escape closes the list to edit.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.lineEdit().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if (
            obj is self.lineEdit()
            and event.type() == QEvent.Type.MouseButtonPress
            and not self.view().isVisible()
        ):
            self.showPopup()
        return super().eventFilter(obj, event)


class SelectAllLineEdit(QLineEdit):
    """A line edit that selects its whole value on focus.

    A lead or owner arrives pre-filled from the name pool; selecting it all
    lets the user overtype the real person's name in one motion. The select
    is deferred a tick because Qt's own mouse handling would otherwise clear
    the selection right after focus-in.
    """

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)
