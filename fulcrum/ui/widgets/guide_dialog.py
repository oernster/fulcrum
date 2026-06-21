"""A dialog showing the planner's guide: the path to a stronger org."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
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
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog
from fulcrum.ui.widgets.move_preview_dialog import MovePreviewDialog

_MIN_WIDTH = 560
_MIN_HEIGHT = 420
_GROW_TOGGLE_TEXT = "Allow the organisation to grow (split or add teams)"
_HINT = "Up and Down move between moves; click a move or 🔍 to preview it."
_ALREADY_GOOD = (
    "This organisation is already in good shape; no single move improves it "
    "much from here."
)
_SCORE_DECIMALS = 1
_WIDGET = "widget"
_GROUP = "group"
_FORWARD = 1
_BACK = -1


def _step_text(index: int, step: GuideStep) -> str:
    return (
        f"{index + 1}. {step.move.display_label()}   "
        f"[{step.classification.value}]   "
        f"→ {step.score_after:.{_SCORE_DECIMALS}f}"
    )


class GuideDialog(NeutralDialog):
    """Lists the improving move chain, like a chess engine's best line.

    A checkbox switches between the fixed-size plan and the plan allowed to grow
    the org. Each step is a move button with a magnifier that previews it, as the
    board's move rows are. Tab cycles the checkbox, the moves group then Close
    (and wraps); Up and Down move between the move and magnifier buttons.
    """

    def __init__(
        self,
        guide: Guide,
        growth_guide: Guide | None = None,
        simulator: Simulator | None = None,
        on_play=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guide - path to a stronger org")
        self.setMinimumSize(ui_scale.px(_MIN_WIDTH), ui_scale.px(_MIN_HEIGHT))
        self._guide = guide
        self._growth_guide = growth_guide
        self._simulator = simulator
        self._on_play = on_play
        self._toggle: QCheckBox | None = None
        layout = QVBoxLayout(self)

        heading = QLabel("Path to a stronger org")
        heading.setObjectName("Heading")
        layout.addWidget(heading)
        self._summary = QLabel("")
        self._summary.setObjectName("Muted")
        layout.addWidget(self._summary)
        if growth_guide is not None:
            self._toggle = QCheckBox(_GROW_TOGGLE_TEXT)
            self._toggle.toggled.connect(self._on_growth_toggled)
            layout.addWidget(self._toggle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._rows_holder = QWidget()
        self._rows = QVBoxLayout(self._rows_holder)
        scroll.setWidget(self._rows_holder)
        layout.addWidget(scroll, 1)

        row = QHBoxLayout()
        self._close_button = QPushButton("Close")
        self._close_button.clicked.connect(self.accept)
        row.addStretch()
        row.addWidget(self._close_button)
        layout.addLayout(row)

        self._render(guide)
        QApplication.instance().installEventFilter(self)

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
        move = QPushButton(_step_text(index, step))
        move.setObjectName("MoveButton")
        move.setCursor(Qt.CursorShape.PointingHandCursor)
        move.clicked.connect(lambda _=False, s=step: self._preview(s))
        magnifier = magnifier_button(lambda s=step: self._preview(s))
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(move, 1)
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
        dialog = MovePreviewDialog(
            step.org_before, None, valuation, self._simulator, step.org_before, self
        )
        if dialog.exec() and self._on_play is not None and self._on_play(step.move):
            self.accept()

    def _on_growth_toggled(self, allow_growth: bool) -> None:
        self._render(self._growth_guide if allow_growth else self._guide)

    # Focus ring: checkbox -> moves group -> Close -> wrap; Up and Down move
    # within the moves group (move and magnifier buttons), which is one Tab stop.
    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        if QApplication.activeModalWidget() is not self:
            return False
        key = event.key()
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            shift = key == Qt.Key.Key_Backtab or bool(
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            )
            self._step(_BACK if shift else _FORWARD)
            return True
        focus = QApplication.focusWidget()
        if key == Qt.Key.Key_Down:
            return self._step_within(focus, _FORWARD)
        if key == Qt.Key.Key_Up:
            return self._step_within(focus, _BACK)
        return False

    def done(self, result: int) -> None:
        QApplication.instance().removeEventFilter(self)
        super().done(result)

    def _ring(self) -> list:
        stops = []
        if self._toggle is not None:
            stops.append((_WIDGET, self._toggle))
        stops.append((_GROUP, self._rows_holder))
        stops.append((_WIDGET, self._close_button))
        return stops

    def _focusables(self) -> list:
        return [
            widget
            for widget in self._rows_holder.findChildren(QWidget)
            if widget.focusPolicy() != Qt.FocusPolicy.NoFocus
            and widget.isVisibleTo(self._rows_holder)
            and widget.isEnabled()
        ]

    def _step(self, delta) -> None:
        stops = self._ring()
        index = self._current_index(stops)
        if index < 0:
            index = -1 if delta == _FORWARD else 0
        for _ in range(len(stops)):
            index = (index + delta) % len(stops)
            if self._focus_stop(stops[index]):
                return

    def _current_index(self, stops) -> int:
        focus = QApplication.focusWidget()
        if focus is None:
            return -1
        for index, (kind, target) in enumerate(stops):
            if kind == _WIDGET and target is focus:
                return index
            if kind == _GROUP and target.isAncestorOf(focus):
                return index
        return -1

    def _focus_stop(self, stop) -> bool:
        kind, target = stop
        if kind == _GROUP:
            focusables = self._focusables()
            if not focusables:
                return False
            focusables[0].setFocus(Qt.FocusReason.TabFocusReason)
            return True
        if not (target.isEnabled() and target.isVisible()):
            return False
        target.setFocus(Qt.FocusReason.TabFocusReason)
        return True

    def _step_within(self, focus, delta) -> bool:
        focusables = self._focusables()
        if focus in focusables and len(focusables) > 1:
            index = (focusables.index(focus) + delta) % len(focusables)
            focusables[index].setFocus(Qt.FocusReason.TabFocusReason)
            return True
        return False
