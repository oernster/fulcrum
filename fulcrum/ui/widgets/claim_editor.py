"""A table widget for authority claims on the org's teams.

Each row picks a claimant (any team or unit, or an unmodelled label kept as
a literal entry) and the team whose decisions it claims, which is how
matrix and dual-reporting structure is drawn. Legality comes from an
injected callback (the draft's can_claim), so the rule lives in the gated
application layer; an illegal row is ignored on OK and flagged in red while
it stands, mirroring the dependency table.

The rows are plain items and the pick combos exist only while a cell is
being edited (node_cell_delegate), so a heavily claimed organisation
populates in linear time instead of hanging the GUI thread.
"""

from __future__ import annotations

from collections.abc import Callable

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

from fulcrum.application.dto import ClaimSpec
from fulcrum.ui.widgets.node_cell_delegate import NODE_ID_ROLE, NodeComboDelegate

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
        self._claimant_labels: dict[str, str] = {}
        self._subject_labels: dict[str, str] = {}
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
        # A claimant may be a plain unmodelled label, kept as a literal entry.
        self._table.setItemDelegateForColumn(
            _COL_CLAIMANT,
            NodeComboDelegate(
                lambda: self._claimant_options, self._table, allow_free_value=True
            ),
        )
        self._table.setItemDelegateForColumn(
            _COL_SUBJECT, NodeComboDelegate(lambda: self._subject_options, self._table)
        )
        self._table.itemChanged.connect(self._on_item_changed)
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
        """Update the node choices, relabelling rows whose nodes renamed."""
        self._claimant_options = list(claimants)
        self._subject_options = list(subjects)
        self._claimant_labels = dict(self._claimant_options)
        self._subject_labels = dict(self._subject_options)
        self._filling = True
        for row in range(self._table.rowCount()):
            for column, labels in (
                (_COL_CLAIMANT, self._claimant_labels),
                (_COL_SUBJECT, self._subject_labels),
            ):
                item = self._table.item(row, column)
                node_id = item.data(NODE_ID_ROLE)
                if node_id in labels:
                    item.setText(labels[node_id])
        self._filling = False
        self._revalidate()

    def set_claims(self, specs) -> None:
        """Replace the rows with the given claim specs."""
        specs = list(specs)
        self._filling = True
        self._table.setUpdatesEnabled(False)
        self._table.setRowCount(0)
        self._table.setRowCount(len(specs))
        for row, spec in enumerate(specs):
            self._set_item(row, _COL_CLAIMANT, spec.claimant, self._claimant_labels)
            self._set_item(row, _COL_SUBJECT, spec.subject, self._subject_labels)
        self._table.setUpdatesEnabled(True)
        self._filling = False
        self._revalidate()

    def _set_item(
        self, row: int, column: int, node_id: str, labels: dict[str, str]
    ) -> None:
        # An unmodelled claimant (or a deleted node) shows itself as the
        # literal text, so a round trip never rewrites it.
        item = QTableWidgetItem(labels.get(node_id, node_id))
        item.setData(NODE_ID_ROLE, node_id)
        self._table.setItem(row, column, item)

    def claims(self) -> tuple[ClaimSpec, ...]:
        specs = []
        seen: set[tuple[str, str]] = set()
        for row in range(self._table.rowCount()):
            claimant = self._table.item(row, _COL_CLAIMANT).data(NODE_ID_ROLE)
            subject = self._table.item(row, _COL_SUBJECT).data(NODE_ID_ROLE)
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

    def _on_item_changed(self, _item) -> None:
        if not self._filling:
            self._revalidate()

    def _revalidate(self) -> None:
        """Flag rows whose pairing is illegal; they are ignored on OK."""
        invalid = sum(
            1
            for row in range(self._table.rowCount())
            if not self._pair_ok(
                self._table.item(row, _COL_CLAIMANT).data(NODE_ID_ROLE),
                self._table.item(row, _COL_SUBJECT).data(NODE_ID_ROLE),
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
        self._set_item(row, _COL_CLAIMANT, "", self._claimant_labels)
        self._set_item(row, _COL_SUBJECT, "", self._subject_labels)
        self._filling = False
        self._revalidate()
        self._table.setCurrentCell(row, _COL_CLAIMANT)
        self._table.editItem(self._table.item(row, _COL_CLAIMANT))

    def _remove_row(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
            self._revalidate()
