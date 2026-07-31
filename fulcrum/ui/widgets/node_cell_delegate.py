"""Item delegates for the org editor's node-picking tables.

The dependency and claim tables used to hold a live QComboBox in every
cell, which priced a thousand-row organisation at millions of combo-item
inserts and hung the GUI thread. The tables now hold plain items (the
label as display text, the node id in the user role) and a combo exists
only while one cell is being edited, so populating a table costs a row
insert per row and the option list is walked once per opened editor.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QSpinBox, QStyledItemDelegate

# The item role carrying the picked node's id beside its display label.
NODE_ID_ROLE = Qt.ItemDataRole.UserRole


class NodeComboDelegate(QStyledItemDelegate):
    """Edits a cell as a combo over the current node options.

    options is a zero-argument callable returning (node_id, label) pairs,
    read when an editor opens so the list is always current. With
    allow_free_value an id that matches no option (an unmodelled claimant
    such as a chapter label) stays selectable as a literal entry, so a
    round trip never rewrites it to whatever sat first in the list.
    """

    def __init__(
        self,
        options: Callable[[], list[tuple[str, str]]],
        parent=None,
        allow_free_value: bool = False,
    ) -> None:
        super().__init__(parent)
        self._options = options
        self._allow_free_value = allow_free_value

    def createEditor(self, parent, option, index) -> QComboBox:
        combo = QComboBox(parent)
        for node_id, label in self._options():
            combo.addItem(label, node_id)
        current = index.data(NODE_ID_ROLE)
        if current and self._allow_free_value and combo.findData(current) < 0:
            combo.addItem(current, current)
        return combo

    def setEditorData(self, editor, index) -> None:
        position = editor.findData(index.data(NODE_ID_ROLE))
        if position >= 0:
            editor.setCurrentIndex(position)

    def setModelData(self, editor, model, index) -> None:
        model.setData(index, editor.currentText(), Qt.ItemDataRole.DisplayRole)
        model.setData(index, editor.currentData(), NODE_ID_ROLE)


class SpinCellDelegate(QStyledItemDelegate):
    """Edits an integer cell with a bounded spinbox."""

    def __init__(self, maximum: int, parent=None) -> None:
        super().__init__(parent)
        self._maximum = maximum

    def createEditor(self, parent, option, index) -> QSpinBox:
        spin = QSpinBox(parent)
        spin.setRange(0, self._maximum)
        return spin
