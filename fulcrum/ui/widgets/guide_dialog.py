"""A dialog showing the planner's guide: the path to a stronger org."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.dto import MoveValuation
from fulcrum.application.interfaces import Simulator
from fulcrum.application.planner import Guide, GuideStep
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.board_renderers import clear_layout, magnifier_button
from fulcrum.ui.widgets.move_preview_dialog import MovePreviewDialog

_MIN_WIDTH = 560
_MIN_HEIGHT = 420
_GROW_TOGGLE_TEXT = "Allow the organisation to grow (split or add teams)"
_HINT = "🔍 previews a move."
_ALREADY_GOOD = (
    "This organisation is already in good shape; no single move improves it "
    "much from here."
)
_SCORE_DECIMALS = 1


def _step_text(index: int, step: GuideStep) -> str:
    return (
        f"{index + 1}. {step.move.display_label()}   "
        f"[{step.classification.value}]   "
        f"→ {step.score_after:.{_SCORE_DECIMALS}f}"
    )


class GuideDialog(QDialog):
    """Lists the improving move chain, like a chess engine's best line.

    When a growth_guide is supplied a checkbox switches between the fixed-size
    plan and the plan allowed to grow the org. Each step carries a real magnifier
    button, tabbable and amber-on-hover, that previews the move as the board does.
    """

    def __init__(
        self,
        guide: Guide,
        growth_guide: Guide | None = None,
        simulator: Simulator | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guide - path to a stronger org")
        self.setMinimumSize(ui_scale.px(_MIN_WIDTH), ui_scale.px(_MIN_HEIGHT))
        self._guide = guide
        self._growth_guide = growth_guide
        self._simulator = simulator
        layout = QVBoxLayout(self)

        heading = QLabel("Path to a stronger org")
        heading.setObjectName("Heading")
        layout.addWidget(heading)
        self._summary = QLabel("")
        self._summary.setObjectName("Muted")
        layout.addWidget(self._summary)
        if growth_guide is not None:
            toggle = QCheckBox(_GROW_TOGGLE_TEXT)
            toggle.toggled.connect(self._on_growth_toggled)
            layout.addWidget(toggle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._rows_holder = QWidget()
        self._rows = QVBoxLayout(self._rows_holder)
        scroll.setWidget(self._rows_holder)
        layout.addWidget(scroll, 1)

        row = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        row.addStretch()
        row.addWidget(close_button)
        layout.addLayout(row)

        self._render(guide)

    def _render(self, guide: Guide) -> None:
        clear_layout(self._rows)
        self._summary.setText(
            f"Start: {guide.start_score:.{_SCORE_DECIMALS}f}    "
            f"Final: {guide.final_score:.{_SCORE_DECIMALS}f}"
        )
        if not guide.steps:
            note = QLabel(_ALREADY_GOOD)
            note.setObjectName("Muted")
            note.setWordWrap(True)
            self._rows.addWidget(note)
            self._rows.addStretch()
            return
        hint = QLabel(_HINT)
        hint.setObjectName("Muted")
        self._rows.addWidget(hint)
        for index, step in enumerate(guide.steps):
            self._rows.addWidget(self._step_row(index, step))
        self._rows.addStretch()

    def _step_row(self, index: int, step: GuideStep) -> QWidget:
        label = QLabel(_step_text(index, step))
        label.setWordWrap(True)
        magnifier = magnifier_button(lambda s=step: self._preview(s))
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(label, 1)
        row.addWidget(magnifier)
        holder = QWidget()
        holder.setLayout(row)
        return holder

    def _preview(self, step: GuideStep) -> None:
        if self._simulator is None:
            return
        valuation = MoveValuation(
            step.move, step.score_before, step.score_after, step.classification
        )
        MovePreviewDialog(
            step.org_before, None, valuation, self._simulator, step.org_before, self
        ).exec()

    def _on_growth_toggled(self, allow_growth: bool) -> None:
        self._render(self._growth_guide if allow_growth else self._guide)
