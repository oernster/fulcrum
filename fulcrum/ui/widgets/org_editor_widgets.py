"""Leaf cell builders for the org editor.

Small, self-contained widget and value builders the editor's tree rows are made
from. They hold no editor state, so they live here to keep the editor module
itself under the structural line limit.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidgetItem,
    QWidget,
)

from fulcrum.domain.models import GROUP_CATEGORIES
from fulcrum.ui import ui_scale

_HEADING = "Heading"
_TREE_ACTION = "TreeAction"
_ACTION_BUTTON_W = 30
_ACTION_BUTTON_H = 18


def labelled(label: QLabel) -> QLabel:
    """Tag a label as a heading for the shared stylesheet."""
    label.setObjectName(_HEADING)
    return label


def default_category(parent: QTreeWidgetItem | None) -> str:
    """The group tier suggested for a new group at the given parent's depth."""
    depth = 0
    node = parent
    while node is not None:
        depth += 1
        node = node.parent()
    return GROUP_CATEGORIES[min(depth, len(GROUP_CATEGORIES) - 1)]


def centered(widget: QWidget) -> QWidget:
    """Wrap a widget in a holder that centres it within its cell."""
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.addStretch()
    row.addWidget(widget)
    row.addStretch()
    return holder


def action_button(glyph: str, tip: str) -> QPushButton:
    """A compact +/- row-action button."""
    button = QPushButton(glyph)
    button.setObjectName(_TREE_ACTION)
    button.setToolTip(tip)
    button.setFixedSize(ui_scale.px(_ACTION_BUTTON_W), ui_scale.px(_ACTION_BUTTON_H))
    return button
