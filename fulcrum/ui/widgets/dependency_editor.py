"""A small table widget for the dependencies between teams in an org.

Each row picks an upstream and a downstream team and a delay; the available
teams are kept in sync as the org editor adds or removes teams, so a row always
references teams that still exist.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
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


class DependencyEditor(QWidget):
    """Edits the directed dependencies (with delays) between the org's teams."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._teams: list[tuple[str, str]] = []
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, len(_HEADERS))
        self._table.setHorizontalHeaderLabels(list(_HEADERS))
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table)
        row = QHBoxLayout()
        add = QPushButton("Add dependency")
        add.clicked.connect(self._add_row)
        remove = QPushButton("Remove dependency")
        remove.clicked.connect(self._remove_row)
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch()
        layout.addLayout(row)

    def set_teams(self, teams) -> None:
        """Update the team choices, preserving each row's current selection."""
        self._teams = list(teams)
        for row in range(self._table.rowCount()):
            self._fill_combo(self._table.cellWidget(row, _COL_UP))
            self._fill_combo(self._table.cellWidget(row, _COL_DOWN))

    def dependencies(self) -> tuple[DependencySpec, ...]:
        specs = []
        for row in range(self._table.rowCount()):
            upstream = self._table.cellWidget(row, _COL_UP).currentData()
            downstream = self._table.cellWidget(row, _COL_DOWN).currentData()
            delay = self._table.cellWidget(row, _COL_DELAY).value()
            if upstream and downstream and upstream != downstream:
                specs.append(DependencySpec(upstream, downstream, delay))
        return tuple(specs)

    def _fill_combo(self, combo: QComboBox) -> None:
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for team_id, name in self._teams:
            combo.addItem(name, team_id)
        index = combo.findData(previous)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _new_combo(self) -> QComboBox:
        combo = QComboBox()
        self._fill_combo(combo)
        return combo

    def _add_row(self) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setCellWidget(row, _COL_UP, self._new_combo())
        self._table.setCellWidget(row, _COL_DOWN, self._new_combo())
        delay = QSpinBox()
        delay.setRange(0, _MAX_DELAY)
        self._table.setCellWidget(row, _COL_DELAY, delay)

    def _remove_row(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
