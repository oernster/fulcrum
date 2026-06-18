"""Edit a loaded plan: reorder or remove moves and re-evaluate before re-export.

Editing can invalidate later moves, so the list flags the first move that no
longer applies and everything after it, and the footer shows the re-evaluated
final score only while the whole sequence still applies.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

from fulcrum.application import plan_edit
from fulcrum.application.dto import Plan
from fulcrum.application.interfaces import Simulator
from fulcrum.application.plan import build_plan_report
from fulcrum.ui import ui_scale

_MIN_WIDTH = 620
_MIN_HEIGHT = 520
_INVALID_SUFFIX = "   [invalid after edit]"
_OK_SCORE = "Re-evaluated final score: {0:.1f} / 100"
_BAD_SCORE = "Sequence is invalid after this edit; trimming on save will fix it."


class PlanEditorDialog(QDialog):
    """Reorders and removes a plan's moves, re-scoring as it goes."""

    def __init__(self, plan: Plan, simulator: Simulator, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit plan")
        self.setMinimumSize(ui_scale.px(_MIN_WIDTH), ui_scale.px(_MIN_HEIGHT))
        self._initial_org = plan.initial_org
        self._moves = plan.moves
        self._simulator = simulator

        layout = QVBoxLayout(self)
        self._list = QListWidget()
        layout.addWidget(self._list, 1)
        layout.addLayout(self._build_buttons())
        self._status = QLabel("")
        self._status.setObjectName("Muted")
        layout.addWidget(self._status)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh()

    def edited_moves(self) -> tuple:
        return self._moves

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        for label, slot in (
            ("Move up", self._up),
            ("Move down", self._down),
            ("Remove", self._remove),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            row.addWidget(button)
        row.addStretch()
        return row

    def _up(self) -> None:
        index = self._list.currentRow()
        if index >= 0:
            self._moves = plan_edit.moved_up(self._moves, index)
            self._refresh(index - 1)

    def _down(self) -> None:
        index = self._list.currentRow()
        if index >= 0:
            self._moves = plan_edit.moved_down(self._moves, index)
            self._refresh(index + 1)

    def _remove(self) -> None:
        index = self._list.currentRow()
        if index >= 0:
            self._moves = plan_edit.without_move(self._moves, index)
            self._refresh(index)

    def _refresh(self, select: int = 0) -> None:
        self._list.clear()
        for description, valid in plan_edit.annotate(self._initial_org, self._moves):
            self._list.addItem(description if valid else description + _INVALID_SUFFIX)
        if self._moves:
            self._list.setCurrentRow(max(0, min(select, len(self._moves) - 1)))
        self._update_status()

    def _update_status(self) -> None:
        if plan_edit.first_invalid_index(self._initial_org, self._moves) is not None:
            self._status.setText(_BAD_SCORE)
            return
        report = build_plan_report(self._initial_org, self._moves, self._simulator)
        self._status.setText(_OK_SCORE.format(report.final_score))
