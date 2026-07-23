"""Explorer-style drag and drop for the org editor's tree.

Dropping onto a unit moves the dragged item inside it as its first child, so
it lands indented directly under the unit's row; dropping in the upper or
lower band of a unit row inserts beside it; a team row simply splits into an
upper and lower half (nothing can drop inside a team, so there is no dead
zone). Holding Ctrl copies instead of moving. Legality is delegated to the
draft (via can_place), so an illegal drop (into the item's own subtree or a
tier under a lower tier) shows the forbidden cursor exactly as a file manager
would. The tree never moves rows itself; the drop is handed to the pane,
which updates the draft and rebuilds, so the view always reflects the model.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget

_ROLE_ID = int(Qt.ItemDataRole.UserRole)
# The top and bottom band of a unit row (as a fraction of its height) that
# means "insert beside" rather than "drop inside".
_BESIDE_BAND = 4
_FIRST_CHILD = 0


class DraftTree(QTreeWidget):
    """A tree whose drags are validated and applied against the org draft."""

    def __init__(self, can_place, on_drop, is_container, parent=None) -> None:
        super().__init__(parent)
        self._can_place = can_place
        self._on_drop = on_drop
        self._is_container = is_container
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def dragMoveEvent(self, event) -> None:
        super().dragMoveEvent(event)
        placement = self._placement(event.position().toPoint())
        source = self._dragged_id()
        if source and placement is not None and self._can_place(source, placement[0]):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        placement = self._placement(event.position().toPoint())
        source = self._dragged_id()
        if not source or placement is None or not self._can_place(source, placement[0]):
            event.ignore()
            return
        parent_id, index = placement
        copy = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()
        # Deferred one tick: the handler rebuilds the tree and deleting items
        # while Qt is still unwinding the drop would touch freed rows.
        QTimer.singleShot(0, lambda: self._on_drop(source, parent_id, index, copy))

    def _dragged_id(self) -> str:
        item = self.currentItem()
        return item.data(0, _ROLE_ID) if item is not None else ""

    def _placement(self, pos):
        """(parent_id, index) for a drop: inside a unit, beside a row or root."""
        item = self.itemAt(pos)
        if item is None:
            return (None, None)
        rect = self.visualItemRect(item)
        node_id = item.data(0, _ROLE_ID)
        if self._is_container(node_id):
            margin = max(1, rect.height() // _BESIDE_BAND)
            if pos.y() <= rect.top() + margin:
                return self._beside(item, 0)
            if pos.y() >= rect.bottom() - margin:
                return self._beside(item, 1)
            # Into the unit, as its FIRST child: the dropped item lands
            # indented directly under the unit's own row.
            return (node_id, _FIRST_CHILD)
        # A team row cannot be dropped into, so it splits into halves with no
        # dead zone: upper half inserts before it, lower half after it.
        if pos.y() <= rect.center().y():
            return self._beside(item, 0)
        return self._beside(item, 1)

    def _beside(self, item, offset: int):
        parent = item.parent()
        if parent is None:
            return (None, self.indexOfTopLevelItem(item) + offset)
        return (parent.data(0, _ROLE_ID), parent.indexOfChild(item) + offset)
