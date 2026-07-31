"""A table widget for the dependencies between the org's items.

Each row picks an upstream and a downstream node (a team or a whole unit at
any level) and a delay; the available nodes are kept in sync as the org
editor changes structure, so a row always references items that still exist.
Pair legality comes from an injected callback (the draft's can_depend), so
the rule lives in the gated application layer; an illegal row is ignored on
OK and flagged in red while it stands.

The rows are plain items and the pick combos exist only while a cell is
being edited (node_cell_delegate), so a thousand-dependency organisation
populates in linear time instead of hanging the GUI thread.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.dto import DependencySpec
from fulcrum.ui.widgets.node_cell_delegate import (
    NODE_ID_ROLE,
    NodeComboDelegate,
    SpinCellDelegate,
)

_HEADERS = ("Upstream (waited on)", "Downstream (waits)", "Delay (turns)")
_COL_UP = 0
_COL_DOWN = 1
_COL_DELAY = 2
_MAX_DELAY = 20
_INVALID_ROW_REASON = (
    "ignored: an item cannot depend on itself or on its own container or " "contents."
)


class DependencyEditor(QWidget):
    """Edits the directed dependencies (with delays) between org items."""

    def __init__(
        self,
        can_pair: Callable[[str, str], bool] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._can_pair = can_pair
        self._options: list[tuple[str, str]] = []
        self._labels: dict[str, str] = {}
        self._filling = False
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, len(_HEADERS))
        self._table.setHorizontalHeaderLabels(list(_HEADERS))
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        node_picker = NodeComboDelegate(lambda: self._options, self._table)
        self._table.setItemDelegateForColumn(_COL_UP, node_picker)
        self._table.setItemDelegateForColumn(_COL_DOWN, node_picker)
        self._table.setItemDelegateForColumn(
            _COL_DELAY, SpinCellDelegate(_MAX_DELAY, self._table)
        )
        self._table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._table)
        self._invalid_note = QLabel("")
        self._invalid_note.setObjectName("BlockedReason")
        self._invalid_note.setWordWrap(True)
        self._invalid_note.setVisible(False)
        layout.addWidget(self._invalid_note)
        row = QHBoxLayout()
        add = QPushButton("Add dependency")
        add.clicked.connect(self._add_row)
        remove = QPushButton("Remove dependency")
        remove.clicked.connect(self._remove_row)
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch()
        layout.addLayout(row)

    def set_options(self, options) -> None:
        """Update the node choices, relabelling rows whose nodes renamed."""
        self._options = list(options)
        self._labels = dict(self._options)
        self._filling = True
        for row in range(self._table.rowCount()):
            for column in (_COL_UP, _COL_DOWN):
                item = self._table.item(row, column)
                node_id = item.data(NODE_ID_ROLE)
                if node_id in self._labels:
                    item.setText(self._labels[node_id])
        self._filling = False
        self._revalidate()

    def set_dependencies(self, specs) -> None:
        """Replace the rows with the given dependency specs."""
        specs = list(specs)
        self._filling = True
        self._table.setUpdatesEnabled(False)
        self._table.setRowCount(0)
        self._table.setRowCount(len(specs))
        for row, spec in enumerate(specs):
            self._set_node_item(row, _COL_UP, spec.upstream)
            self._set_node_item(row, _COL_DOWN, spec.downstream)
            delay = QTableWidgetItem()
            delay.setData(Qt.ItemDataRole.EditRole, spec.propagation_delay)
            self._table.setItem(row, _COL_DELAY, delay)
        self._table.setUpdatesEnabled(True)
        self._filling = False
        self._revalidate()

    def _set_node_item(self, row: int, column: int, node_id: str) -> None:
        # An id with no current option (a deleted node) keeps itself as the
        # visible text; the row reads invalid and is ignored on OK.
        item = QTableWidgetItem(self._labels.get(node_id, node_id))
        item.setData(NODE_ID_ROLE, node_id)
        self._table.setItem(row, column, item)

    def dependencies(self) -> tuple[DependencySpec, ...]:
        specs = []
        for row in range(self._table.rowCount()):
            upstream = self._table.item(row, _COL_UP).data(NODE_ID_ROLE)
            downstream = self._table.item(row, _COL_DOWN).data(NODE_ID_ROLE)
            delay = self._table.item(row, _COL_DELAY).data(Qt.ItemDataRole.EditRole)
            if self._pair_ok(upstream, downstream):
                specs.append(DependencySpec(upstream, downstream, int(delay or 0)))
        return tuple(specs)

    def _pair_ok(self, upstream, downstream) -> bool:
        if not upstream or not downstream:
            return False
        if self._can_pair is not None:
            return self._can_pair(upstream, downstream)
        return upstream != downstream

    def _on_item_changed(self, _item) -> None:
        if not self._filling:
            self._revalidate()

    def _revalidate(self) -> None:
        """Flag rows whose pairing is illegal; they are ignored on OK."""
        invalid = sum(
            1
            for row in range(self._table.rowCount())
            if not self._pair_ok(
                self._table.item(row, _COL_UP).data(NODE_ID_ROLE),
                self._table.item(row, _COL_DOWN).data(NODE_ID_ROLE),
            )
        )
        if invalid:
            noun = "row is" if invalid == 1 else "rows are"
            self._invalid_note.setText(f"{invalid} {noun} {_INVALID_ROW_REASON}")
        self._invalid_note.setVisible(bool(invalid))

    def _add_row(self) -> None:
        row = self._table.rowCount()
        self._filling = True
        self._table.insertRow(row)
        self._set_node_item(row, _COL_UP, "")
        self._set_node_item(row, _COL_DOWN, "")
        delay = QTableWidgetItem()
        delay.setData(Qt.ItemDataRole.EditRole, 0)
        self._table.setItem(row, _COL_DELAY, delay)
        self._filling = False
        self._revalidate()
        self._table.setCurrentCell(row, _COL_UP)
        self._table.editItem(self._table.item(row, _COL_UP))

    def _remove_row(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
            self._revalidate()
