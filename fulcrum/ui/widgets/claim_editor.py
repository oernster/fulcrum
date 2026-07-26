"""A small table widget for authority claims on the org's teams.

Each row picks a claimant (any team or unit) and the team whose decisions it
claims, which is how matrix and dual-reporting structure is drawn. Legality
comes from an injected callback (the draft's can_claim), so the rule lives in
the gated application layer; an illegal row is ignored on OK and flagged in
red while it stands, mirroring the dependency table.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.dto import ClaimSpec

_HEADERS = ("Claimant (also claims the decisions)", "Team (whose decisions)")
_COL_CLAIMANT = 0
_COL_SUBJECT = 1
_INVALID_ROW_REASON = (
    "ignored: a claimant must be a different existing item, the claimed side "
    "must be a team and duplicates are dropped."
)


class ClaimEditor(QWidget):
    """Edits the authority claims (claimant, team) recorded on the draft."""

    def __init__(
        self,
        can_claim: Callable[[str, str], bool] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._can_claim = can_claim
        self._claimant_options: list[tuple[str, str]] = []
        self._subject_options: list[tuple[str, str]] = []
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
        add = QPushButton("Add claim")
        add.clicked.connect(self._add_row)
        remove = QPushButton("Remove claim")
        remove.clicked.connect(self._remove_row)
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch()
        layout.addLayout(row)

    def set_options(self, claimants, subjects) -> None:
        """Update the node choices, preserving each row's current selection."""
        self._claimant_options = list(claimants)
        self._subject_options = list(subjects)
        for row in range(self._table.rowCount()):
            self._fill_combo(
                self._table.cellWidget(row, _COL_CLAIMANT), self._claimant_options
            )
            self._fill_combo(
                self._table.cellWidget(row, _COL_SUBJECT), self._subject_options
            )
        self._revalidate()

    def set_claims(self, specs) -> None:
        """Replace the rows with the given claim specs."""
        self._table.setRowCount(0)
        for spec in specs:
            self._add_row()
            row = self._table.rowCount() - 1
            self._select(self._table.cellWidget(row, _COL_CLAIMANT), spec.claimant)
            self._select(self._table.cellWidget(row, _COL_SUBJECT), spec.subject)
        self._revalidate()

    def _select(self, combo: QComboBox, node_id: str) -> None:
        index = combo.findData(node_id)
        if index < 0:
            # An imported claimant may be a plain label rather than a modelled
            # node; keep it as a literal entry so a round trip never rewrites
            # it to whatever sat first in the list.
            combo.addItem(node_id, node_id)
            index = combo.findData(node_id)
        combo.setCurrentIndex(index)

    def claims(self) -> tuple[ClaimSpec, ...]:
        specs = []
        seen: set[tuple[str, str]] = set()
        for row in range(self._table.rowCount()):
            claimant = self._table.cellWidget(row, _COL_CLAIMANT).currentData()
            subject = self._table.cellWidget(row, _COL_SUBJECT).currentData()
            if (claimant, subject) in seen:
                continue
            if self._pair_ok(claimant, subject):
                seen.add((claimant, subject))
                specs.append(ClaimSpec(claimant, subject))
        return tuple(specs)

    def _pair_ok(self, claimant, subject) -> bool:
        if not claimant or not subject:
            return False
        if self._can_claim is not None:
            return self._can_claim(claimant, subject)
        return claimant != subject

    def _revalidate(self) -> None:
        """Flag rows whose pairing is illegal; they are ignored on OK."""
        invalid = sum(
            1
            for row in range(self._table.rowCount())
            if not self._pair_ok(
                self._table.cellWidget(row, _COL_CLAIMANT).currentData(),
                self._table.cellWidget(row, _COL_SUBJECT).currentData(),
            )
        )
        if invalid:
            noun = "row is" if invalid == 1 else "rows are"
            self._invalid_note.setText(f"{invalid} {noun} {_INVALID_ROW_REASON}")
        self._invalid_note.setVisible(bool(invalid))

    def _fill_combo(self, combo: QComboBox, options) -> None:
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for node_id, label in options:
            combo.addItem(label, node_id)
        if previous:
            index = combo.findData(previous)
            if index < 0:
                # Preserve an unmodelled (free-text) claimant across refills.
                combo.addItem(previous, previous)
                index = combo.findData(previous)
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _new_combo(self, options) -> QComboBox:
        combo = QComboBox()
        self._fill_combo(combo, options)
        combo.currentIndexChanged.connect(self._revalidate)
        return combo

    def _add_row(self) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setCellWidget(
            row, _COL_CLAIMANT, self._new_combo(self._claimant_options)
        )
        self._table.setCellWidget(
            row, _COL_SUBJECT, self._new_combo(self._subject_options)
        )
        self._revalidate()

    def _remove_row(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
            self._revalidate()
