"""A scrollable, height-stable note shown under the org map.

The note area is fixed to the height of the tallest move note at the current
width (so changing its text never reflows the board) but capped to a few lines,
and it scrolls when a note is taller than the cap. On a short screen the capped
height keeps the map visible while the full note stays reachable by scrolling.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea

from fulcrum.application.move_text import move_note
from fulcrum.domain.moves import MoveKind
from fulcrum.ui import ui_scale

_MIN_HEIGHT = 40
_PAD = 10
_MAX_LINES = 4
_WRAP_FLAG = int(Qt.TextFlag.TextWordWrap)


_LAST_MOVE_PREFIX = "Last move played"
_EARLIER_RUN_SUFFIX = " (in an earlier run)"


class MoveNoteView(QScrollArea):
    """The last move's note: height-stable, capped and scrollable when long."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._label = QLabel("")
        self._label.setObjectName("Muted")
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setWidget(self._label)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(ui_scale.px(_MIN_HEIGHT))

    def show_last_move(self, session) -> None:
        """Say what the record's last move was, or nothing without one.

        The note says exactly what it explains: with history persisting
        across runs, the last move is not necessarily one just played,
        so a bare explanation would sit there with no context at all.
        """
        if session is None or not session.history:
            self.set_text("")
            return
        history = session.history
        last = history[-1]
        earlier = len(history) <= session.prior_history_count
        run = _EARLIER_RUN_SUFFIX if earlier else ""
        self.set_text(
            f"{_LAST_MOVE_PREFIX}{run}: {last.display_label()}. "
            f"{move_note(last.kind)}"
        )

    def set_text(self, text: str) -> None:
        self._label.setText(text)
        self._fit_label()

    def reserve_height(self) -> None:
        """Fix the area to the tallest note at the current width, capped."""
        width = self.viewport().width()
        if width <= 0:
            return
        metrics = self._label.fontMetrics()
        tallest = max(
            metrics.boundingRect(0, 0, width, 0, _WRAP_FLAG, move_note(k)).height()
            for k in MoveKind
        )
        cap = metrics.lineSpacing() * _MAX_LINES
        self.setFixedHeight(min(tallest, cap) + ui_scale.px(_PAD))
        self._fit_label()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_label()

    def _fit_label(self) -> None:
        # Claim the label's full wrapped height so the area shows a scrollbar
        # when a note is taller than the capped height.
        width = self.viewport().width()
        if width <= 0:
            return
        needed = self._label.heightForWidth(width)
        if needed > 0:
            self._label.setMinimumHeight(needed)
