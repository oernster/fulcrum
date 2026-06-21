"""The central board: map, score, signals and the move palette for a position."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.dto import MoveValuation
from fulcrum.application.game_session import GameSession
from fulcrum.application.move_text import describe_move, move_note
from fulcrum.domain.hierarchy import total_headcount
from fulcrum.domain.moves import MoveKind
from fulcrum.domain.signals import SignalReading
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.definition_popover import DefinitionPopover
from fulcrum.ui.widgets.org_map_view import OrgMapView

_SCORE_DECIMALS = 1
_VALUE_DECIMALS = 1
_MAP_CAPTION = "Organisation map"
_MAP_HINT = "click a domain to open"
_MOVES_TOOLTIP = (
    "At a high-level scope the moves are mostly neutral with very small score "
    "gains. To really gain, drill into a domain on the map and play that "
    "section, where the strong moves appear."
)
_MAP_PANE_W = 520
_RIGHT_PANE_W = 480
_RIGHT_PANE_MIN = 360
_MOVES_RIGHT_PAD = 12
_PREVIEW_COLOR = "#fbbf24"
# The per-move note reserves the height of the tallest note at the current
# width (recomputed on resize), so changing its text on hover never reflows the
# layout: that reflow read as a jiggle as the mouse swept across the moves.
_MOVE_NOTE_PAD = 10
_MOVE_NOTE_MIN_HEIGHT = 40
_WRAP_FLAG = int(Qt.TextFlag.TextWordWrap)


def _clear(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


class _MoveButton(QPushButton):
    """A move button that announces hover enter and leave for map previews."""

    entered = Signal()
    left = Signal()

    def enterEvent(self, event) -> None:
        self.entered.emit()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.left.emit()
        super().leaveEvent(event)


class BoardView(QWidget):
    """Renders a GameSession: map, score, signals and clickable candidate moves."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session: GameSession | None = None
        self._popover: DefinitionPopover | None = None

        self._score_label = QLabel("-")
        self._score_label.setObjectName("ScoreValue")
        self._origin_label = QLabel("")
        self._origin_label.setObjectName("Muted")
        self._headcount_label = QLabel("")
        self._headcount_label.setObjectName("Muted")
        self._focus_label = QLabel("")
        self._focus_label.setObjectName("Muted")
        self._focus_label.setWordWrap(True)
        self._focus_label.setVisible(False)
        self._map_caption = QLabel(_MAP_CAPTION)
        self._map_caption.setObjectName("Muted")
        self._map = OrgMapView()
        self._map.drilled.connect(self._on_drilled)
        self._move_note = QLabel("")
        self._move_note.setObjectName("Muted")
        self._move_note.setWordWrap(True)
        self._move_note.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._move_note.setFixedHeight(ui_scale.px(_MOVE_NOTE_MIN_HEIGHT))
        self._signals_row = QVBoxLayout()
        self._moves_box = QVBoxLayout()
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        health = QLabel("Organisational structural health")
        health.setObjectName("Muted")
        layout.addWidget(health)
        layout.addWidget(self._score_label)
        layout.addWidget(self._origin_label)
        layout.addWidget(self._headcount_label)
        layout.addWidget(self._focus_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_map_pane())
        splitter.addWidget(self._build_side_pane())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([ui_scale.px(_MAP_PANE_W), ui_scale.px(_RIGHT_PANE_W)])
        layout.addWidget(splitter, 1)

    def _build_map_pane(self) -> QWidget:
        pane = QWidget()
        column = QVBoxLayout(pane)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self._map_caption)
        column.addWidget(self._map, 1)
        column.addWidget(self._move_note)
        return pane

    def _build_side_pane(self) -> QWidget:
        pane = QWidget()
        pane.setMinimumWidth(ui_scale.px(_RIGHT_PANE_MIN))
        column = QVBoxLayout(pane)
        column.setContentsMargins(0, 0, 0, 0)
        moves_caption = QLabel("Available moves within current scope")
        moves_caption.setObjectName("Muted")
        moves_caption.setToolTip(_MOVES_TOOLTIP)
        column.addWidget(moves_caption)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        moves_holder = QWidget()
        self._moves_box.setContentsMargins(0, 0, ui_scale.px(_MOVES_RIGHT_PAD), 0)
        moves_holder.setLayout(self._moves_box)
        scroll.setWidget(moves_holder)
        column.addWidget(scroll, 1)
        signals_caption = QLabel("Signals to watch")
        signals_caption.setObjectName("Muted")
        column.addWidget(signals_caption)
        signals_holder = QWidget()
        signals_holder.setLayout(self._signals_row)
        column.addWidget(signals_holder)
        return pane

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reserve_move_note_height()

    def _reserve_move_note_height(self) -> None:
        width = self._move_note.width()
        if width <= 0:
            return
        metrics = self._move_note.fontMetrics()
        tallest = max(
            metrics.boundingRect(0, 0, width, 0, _WRAP_FLAG, move_note(k)).height()
            for k in MoveKind
        )
        self._move_note.setFixedHeight(tallest + ui_scale.px(_MOVE_NOTE_PAD))

    def set_session(self, session: GameSession) -> None:
        self._session = session
        session.focus(None)
        self._map.reset_view()
        self.refresh()

    def _on_drilled(self, domain_id) -> None:
        if self._session is None:
            return
        self._session.focus(domain_id)
        self.refresh()

    def refresh(self) -> None:
        if self._session is None:
            return
        self._score_label.setText(f"{self._session.score():.{_SCORE_DECIMALS}f} / 100")
        self._origin_label.setText(
            f"Origin: {self._session.org.origin.value}  ·  "
            f"moves played: {len(self._session.history)}"
        )
        self._headcount_label.setText(
            f"{total_headcount(self._session.org):,} people across "
            f"{len(self._session.org.teams)} teams"
        )
        self._set_focus_note()
        self._map_caption.setText(self._map_caption_text())
        self._map_caption.setStyleSheet("")
        self._map.set_preview(False)
        self._map.set_org(self._session.org)
        self._render_signals(self._session.signals())
        self._render_moves(self._session.candidate_valuations())
        self._set_last_move_note()

    def _map_caption_text(self) -> str:
        if self._session is not None and self._session.org.domains:
            return f"{_MAP_CAPTION} · {_MAP_HINT}"
        return _MAP_CAPTION

    def _set_focus_note(self) -> None:
        focused = self._session.focused_on if self._session is not None else None
        if focused is None:
            self._focus_label.setVisible(False)
            self._focus_label.setStyleSheet("")
            self._focus_label.setText("")
            return
        name = self._focus_domain_name(focused)
        self._focus_label.setText(
            f"Focused on {name}: this score and these moves are the section's. "
            "Use Back on the map to zoom out."
        )
        self._focus_label.setStyleSheet(f"color: {_PREVIEW_COLOR};")
        self._focus_label.setVisible(True)

    def _focus_domain_name(self, domain_id: str) -> str:
        for domain in self._session.org.domains:
            if domain.id == domain_id:
                return domain.name
        return domain_id

    def _render_signals(self, readings: tuple[SignalReading, ...]) -> None:
        _clear(self._signals_row)
        for reading in readings:
            chip = QPushButton(
                f"{reading.definition.label}: "
                f"{reading.value:.{_VALUE_DECIMALS}f} {reading.definition.unit}"
            )
            chip.setObjectName("SignalChip")
            chip.setToolTip(reading.definition.gloss)
            chip.clicked.connect(lambda _=False, r=reading: self._show_definition(r))
            self._signals_row.addWidget(chip)
        self._signals_row.addStretch()

    def _render_moves(self, valuations: tuple[MoveValuation, ...]) -> None:
        _clear(self._moves_box)
        for valuation in valuations:
            description = describe_move(self._session.org, valuation.move)
            button = _MoveButton(
                f"{description}   "
                f"[{valuation.classification.value}]   "
                f"{valuation.delta:+.{_VALUE_DECIMALS}f}"
            )
            button.setObjectName("MoveButton")
            button.clicked.connect(lambda _=False, v=valuation: self._play(v))
            button.entered.connect(lambda v=valuation: self._preview_move(v))
            button.left.connect(self._unpreview_move)
            self._moves_box.addWidget(button)
        self._moves_box.addStretch()

    def _play(self, valuation: MoveValuation) -> None:
        if self._session is None:
            return
        self._session.play(valuation.move)
        self.refresh()

    def _preview_move(self, valuation: MoveValuation) -> None:
        if self._session is None:
            return
        self._map.set_org(self._session.preview(valuation.move))
        self._map.set_preview(True)
        description = describe_move(self._session.org, valuation.move)
        self._map_caption.setText(f"{_MAP_CAPTION} · after: {description}")
        self._map_caption.setStyleSheet(f"color: {_PREVIEW_COLOR};")
        self._move_note.setText(move_note(valuation.move.kind))

    def _unpreview_move(self) -> None:
        if self._session is not None:
            self._map.set_org(self._session.org)
            self._map.set_preview(False)
            self._map_caption.setText(self._map_caption_text())
            self._map_caption.setStyleSheet("")
            self._set_last_move_note()

    def _set_last_move_note(self) -> None:
        if self._session is not None and self._session.history:
            self._move_note.setText(move_note(self._session.history[-1].kind))
        else:
            self._move_note.setText("")

    def _show_definition(self, reading: SignalReading) -> None:
        self._popover = DefinitionPopover(reading.definition, self)
        self._popover.adjustSize()
        self._popover.move(QCursor.pos())
        self._popover.show()
