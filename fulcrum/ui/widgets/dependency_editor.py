"""A small table widget for the dependencies between the org's items.

Each row picks an upstream and a downstream node (a team or a whole unit at
any level) and a delay; the available nodes are kept in sync as the org
editor changes structure, so a row always references items that still exist.
Pair legality comes from an injected callback (the draft's can_depend), so
the rule lives in the gated application layer; an illegal row is ignored on
OK and flagged in red while it stands.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.dto import DependencySpec

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
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, len(_HEADERS))
        self._table.setHorizontalHeaderLabels(list(_HEADERS))
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
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
        """Update the node choices, preserving each row's current selection."""
        self._options = list(options)
        for row in range(self._table.rowCount()):
            self._fill_combo(self._table.cellWidget(row, _COL_UP))
            self._fill_combo(self._table.cellWidget(row, _COL_DOWN))
        self._revalidate()

    def set_dependencies(self, specs) -> None:
        """Replace the rows with the given dependency specs."""
        self._table.setRowCount(0)
        for spec in specs:
            self._add_row()
            row = self._table.rowCount() - 1
            self._select(self._table.cellWidget(row, _COL_UP), spec.upstream)
            self._select(self._table.cellWidget(row, _COL_DOWN), spec.downstream)
            self._table.cellWidget(row, _COL_DELAY).setValue(spec.propagation_delay)
        self._revalidate()

    def _select(self, combo: QComboBox, node_id: str) -> None:
        index = combo.findData(node_id)
        if index >= 0:
            combo.setCurrentIndex(index)

    def dependencies(self) -> tuple[DependencySpec, ...]:
        specs = []
        for row in range(self._table.rowCount()):
            upstream = self._table.cellWidget(row, _COL_UP).currentData()
            downstream = self._table.cellWidget(row, _COL_DOWN).currentData()
            delay = self._table.cellWidget(row, _COL_DELAY).value()
            if self._pair_ok(upstream, downstream):
                specs.append(DependencySpec(upstream, downstream, delay))
        return tuple(specs)

    def _pair_ok(self, upstream, downstream) -> bool:
        if not upstream or not downstream:
            return False
        if self._can_pair is not None:
            return self._can_pair(upstream, downstream)
        return upstream != downstream

    def _revalidate(self) -> None:
        """Flag rows whose pairing is illegal; they are ignored on OK."""
        invalid = sum(
            1
            for row in range(self._table.rowCount())
            if not self._pair_ok(
                self._table.cellWidget(row, _COL_UP).currentData(),
                self._table.cellWidget(row, _COL_DOWN).currentData(),
            )
        )
        if invalid:
            noun = "row is" if invalid == 1 else "rows are"
            self._invalid_note.setText(f"{invalid} {noun} {_INVALID_ROW_REASON}")
        self._invalid_note.setVisible(bool(invalid))

    def _fill_combo(self, combo: QComboBox) -> None:
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for node_id, label in self._options:
            combo.addItem(label, node_id)
        index = combo.findData(previous)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _new_combo(self) -> QComboBox:
        combo = QComboBox()
        self._fill_combo(combo)
        combo.currentIndexChanged.connect(self._revalidate)
        return combo

    def _add_row(self) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setCellWidget(row, _COL_UP, self._new_combo())
        self._table.setCellWidget(row, _COL_DOWN, self._new_combo())
        delay = QSpinBox()
        delay.setRange(0, _MAX_DELAY)
        self._table.setCellWidget(row, _COL_DELAY, delay)
        self._revalidate()

    def _remove_row(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
            self._revalidate()
