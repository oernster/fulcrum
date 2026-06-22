"""The central board: map, score, signals and the move palette for a position."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.dto import MoveValuation
from fulcrum.application.game_session import GameSession
from fulcrum.application.move_text import move_note
from fulcrum.domain.hierarchy import child_domains, total_headcount
from fulcrum.domain.moves import MoveKind
from fulcrum.domain.signals import SignalReading
from fulcrum.domain.simulation import MoveClassification
from fulcrum.ui import ui_scale
from fulcrum.ui.analysis_thread import AnalysisThread
from fulcrum.ui.widgets.board_renderers import clear_layout, move_row, signal_row
from fulcrum.ui.widgets.move_preview_dialog import MovePreviewDialog
from fulcrum.ui.widgets.org_map_view import OrgMapView
from fulcrum.ui.widgets.signal_detail_dialog import SignalDetailDialog

_SCORE_DECIMALS = 1
_MAP_CAPTION = "Organisation map"
_MAP_HINT = "click a domain to open"
_MOVES_TOOLTIP = (
    "At a high-level scope the moves are mostly neutral with very small score "
    "gains. To really gain, drill into a domain on the map and play that "
    "section, where the strong moves appear."
)
_SCOPE_HINT = (
    "Only neutral moves at this scope. Drill into a domain on the map to find "
    "the strong moves that really gain."
)
_OVERVIEW_HINT = (
    "This scope is too large to score live. Drill into a section on the map to "
    "play it, where the score and the strong moves appear."
)
_OVERVIEW_SCORE = "-"
_COMPUTING_SCORE = "..."
_COMPUTING_HINT = "Scoring this section..."
# Show the scoring note only if the analysis outlasts this, so a section that
# scores quickly refreshes without flickering the note in and straight out.
_COMPUTING_DELAY_MS = 200
# Coalesce a flurry of drills into one scoring pass: the score and moves update
# once navigation settles, so rapid drilling never piles up worker threads.
_ANALYSIS_DELAY_MS = 120
_MAP_PANE_W = 520
_RIGHT_PANE_W = 480
_RIGHT_PANE_MIN = 360
_MOVES_RIGHT_PAD = 12
_PREVIEW_COLOR = "#fbbf24"
_UNDO_LABEL = "Take a move back"
_UNDO_TIP = "Undo the last move played"
# The per-move note reserves the height of the tallest note at the current
# width (recomputed on resize), so changing its text on hover never reflows the
# layout: that reflow read as a jiggle as the mouse swept across the moves.
_MOVE_NOTE_PAD = 10
_MOVE_NOTE_MIN_HEIGHT = 40
_WRAP_FLAG = int(Qt.TextFlag.TextWordWrap)


class BoardView(QWidget):
    """Renders a GameSession: map, score, signals and clickable candidate moves."""

    historyChanged = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session: GameSession | None = None

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
        self._undo_button = QPushButton(_UNDO_LABEL)
        self._undo_button.setToolTip(_UNDO_TIP)
        self._undo_button.setEnabled(False)
        self._undo_button.clicked.connect(self.take_back)
        self._signals_row = QVBoxLayout()
        self._moves_box = QVBoxLayout()
        self._moves_holder = QWidget()
        self._signals_holder = QWidget()
        self._analysis_request = 0
        self._analyses: set[AnalysisThread] = set()
        self._scope_active = None
        self._computing_timer = QTimer(self)
        self._computing_timer.setSingleShot(True)
        self._computing_timer.timeout.connect(self._show_computing)
        self._analysis_timer = QTimer(self)
        self._analysis_timer.setSingleShot(True)
        self._analysis_timer.timeout.connect(self._run_analysis)
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
        controls = QHBoxLayout()
        controls.addWidget(self._undo_button)
        controls.addStretch()
        layout.addLayout(controls)

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
        self._scope_hint = QLabel(_SCOPE_HINT)
        self._scope_hint.setObjectName("Muted")
        self._scope_hint.setWordWrap(True)
        self._scope_hint.setStyleSheet(f"color: {_PREVIEW_COLOR};")
        self._scope_hint.setVisible(False)
        column.addWidget(self._scope_hint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._moves_box.setContentsMargins(0, 0, ui_scale.px(_MOVES_RIGHT_PAD), 0)
        self._moves_holder.setLayout(self._moves_box)
        scroll.setWidget(self._moves_holder)
        column.addWidget(scroll, 1)
        signals_caption = QLabel("Signals to watch")
        signals_caption.setObjectName("Muted")
        column.addWidget(signals_caption)
        self._signals_holder.setLayout(self._signals_row)
        column.addWidget(self._signals_holder)
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
        # The map already redrew the new level in its own click handler, so only
        # the scope-dependent parts refresh here: re-rendering the whole map
        # again per drill is what made deep drilling stutter.
        self._session.focus(domain_id)
        self._set_focus_note()
        self._start_analysis()

    def refresh(self) -> None:
        if self._session is None:
            return
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
        self._set_last_move_note()
        self._update_undo()
        self._start_analysis()

    def take_back(self) -> None:
        """Undo the last move played and re-render the position."""
        if self._session is None or not self._session.can_take_back:
            return
        self._session.take_back()
        self.refresh()

    def _update_undo(self) -> None:
        can = self._session is not None and self._session.can_take_back
        self._undo_button.setEnabled(can)
        self.historyChanged.emit(can)

    def nav_targets(self) -> tuple[QWidget, ...]:
        """The board's keyboard-nav stops, in reading order."""
        return (self._undo_button, self._map, self._moves_holder, self._signals_holder)

    def _start_analysis(self) -> None:
        """Debounce scoring so a flurry of drills runs only one analysis."""
        self._analysis_timer.start(_ANALYSIS_DELAY_MS)

    def stop_analysis(self) -> None:
        """Stop pending and running scoring so the app closes without a crash."""
        self._analysis_timer.stop()
        self._computing_timer.stop()
        for worker in tuple(self._analyses):
            worker.wait()

    def _run_analysis(self) -> None:
        if self._session is None:
            return
        self._analysis_request += 1
        worker = AnalysisThread(
            self._analysis_request,
            self._session.org,
            self._session.focused_on,
            self._session.simulator,
        )
        worker.analysed.connect(self._on_analysed)
        worker.finished.connect(lambda w=worker: self._analyses.discard(w))
        worker.finished.connect(worker.deleteLater)
        self._analyses.add(worker)
        self._computing_timer.start(_COMPUTING_DELAY_MS)
        worker.start()

    def _show_computing(self) -> None:
        self._score_label.setText(_COMPUTING_SCORE)
        self._render_signals(())
        self._render_moves(())
        self._scope_hint.setText(_COMPUTING_HINT)
        self._scope_hint.setVisible(True)

    def _on_analysed(self, request: int, analysis) -> None:
        if request != self._analysis_request:
            return
        self._computing_timer.stop()
        if analysis.playable:
            self._render_analysis(analysis)
        else:
            self._render_overview_scope()

    def _render_analysis(self, analysis) -> None:
        self._scope_active = analysis.active
        self._score_label.setText(f"{analysis.score:.{_SCORE_DECIMALS}f} / 100")
        self._render_signals(analysis.signals)
        self._render_moves(analysis.valuations)
        self._update_scope_hint(analysis.valuations)

    def _render_overview_scope(self) -> None:
        self._score_label.setText(_OVERVIEW_SCORE)
        self._render_signals(())
        self._render_moves(())
        self._scope_hint.setText(_OVERVIEW_HINT)
        self._scope_hint.setVisible(True)

    def _update_scope_hint(self, valuations) -> None:
        self._scope_hint.setText(_SCOPE_HINT)
        strong = {MoveClassification.GOOD, MoveClassification.GREAT}
        has_strong = any(v.classification in strong for v in valuations)
        focused = self._session.focused_on
        can_drill = focused is None or bool(child_domains(self._session.org, focused))
        self._scope_hint.setVisible(can_drill and not has_strong)

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
        clear_layout(self._signals_row)
        for reading in readings:
            self._signals_row.addWidget(signal_row(reading, self._open_signal_detail))
        self._signals_row.addStretch()

    def _render_moves(self, valuations: tuple[MoveValuation, ...]) -> None:
        clear_layout(self._moves_box)
        for valuation in valuations:
            row = move_row(
                self._scope_active, valuation, self._play, self._open_move_preview
            )
            self._moves_box.addWidget(row)
        self._moves_box.addStretch()

    def _play(self, valuation: MoveValuation) -> None:
        if self._session is None:
            return
        self._session.play(valuation.move)
        self.refresh()

    def _open_move_preview(self, valuation: MoveValuation) -> None:
        if self._session is None:
            return
        dialog = MovePreviewDialog(
            self._session.org,
            self._session.focused_on,
            valuation,
            self._session.simulator,
            self._scope_active,
            self,
        )
        if dialog.exec():
            self._play(valuation)

    def _set_last_move_note(self) -> None:
        if self._session is not None and self._session.history:
            self._move_note.setText(move_note(self._session.history[-1].kind))
        else:
            self._move_note.setText("")

    def _open_signal_detail(self, reading: SignalReading) -> None:
        SignalDetailDialog(reading, self).exec()
