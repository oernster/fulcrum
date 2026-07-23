"""Leaf widget builders shared by the org editor's tree and inspector panes.

Small, self-contained widget builders holding no editor state, kept here so
the editor modules stay within the structural line limit.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton

from fulcrum.ui import ui_scale

_HEADING = "Heading"
_TREE_ACTION = "TreeAction"
_ACTION_BUTTON_W = 30
_ACTION_BUTTON_H = 18
_DICE_GLYPH = "\N{GAME DIE}"
_DICE_TIP = "Roll a different name"


def labelled(label: QLabel) -> QLabel:
    """Tag a label as a heading for the shared stylesheet."""
    label.setObjectName(_HEADING)
    return label


def action_button(glyph: str, tip: str) -> QPushButton:
    """A compact +/- row-action button."""
    button = QPushButton(glyph)
    button.setObjectName(_TREE_ACTION)
    button.setToolTip(tip)
    button.setFixedSize(ui_scale.px(_ACTION_BUTTON_W), ui_scale.px(_ACTION_BUTTON_H))
    return button


def dice_button() -> QPushButton:
    """The reroll die shown beside a lead or owner field."""
    button = QPushButton(_DICE_GLYPH)
    button.setObjectName("DiceButton")
    button.setToolTip(_DICE_TIP)
    return button


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
