"""The move record: every position to date, walked sequentially.

The exportable HTML presentation's live sibling: the whole record (earlier
runs included) as a list, and a position cursor over the full timeline from
the original organisation to the position after the latest move. The arrow
buttons (or the list) step the cursor; the dialog opens at the latest
position and carries its own keyboard focus ring.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.game_session import record_positions
from fulcrum.application.interfaces import Simulator
from fulcrum.application.move_text import describe_position_change
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move
from fulcrum.shared.resources import find_about_png
from fulcrum.shared.text import SCORE_DECIMALS
from fulcrum.ui import ui_scale
from fulcrum.ui.theme_palettes import DEFAULT_THEME, PALETTES
from fulcrum.ui.widgets.auto_scroller import AutoScroller
from fulcrum.ui.widgets.complete_map_view import CompleteMapView
from fulcrum.ui.widgets.dialog_banner import banner_row
from fulcrum.ui.widgets.dialog_focus_ring import WIDGET_STOP, DialogFocusRing
from fulcrum.ui.widgets.dialog_sizing import initial_size
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog

_TITLE = "Move record"
_MIN_WIDTH = 980
_MIN_HEIGHT = 620
_PARENT_FILL = 0.9
_SCREEN_FILL = 0.85
_LIST_SHARE = 1
_MAP_SHARE = 3
_LIST_PANE_W = 320
_MAP_PANE_W = 860
_EMPTY_TEXT = "No moves have been played yet."
_EARLIER_SUFFIX = "   (earlier run)"
_EARLIER_GLYPH = "⬅️"
_LATER_GLYPH = "➡️"
_EARLIER_TIP = "Show the earlier position"
_LATER_TIP = "Show the later position"
_ORIGINAL_CAPTION = "The original position"
_ORIGINAL_CHANGE = "The organisation as it started, before any move."
_ORIGINAL_ROW = f"0. {_ORIGINAL_CAPTION}"


class MoveRecordDialog(NeutralDialog):
    """Lists the whole record; a cursor walks the positions sequentially."""

    def __init__(
        self,
        initial_org: OrgState,
        history: tuple[Move, ...],
        prior_count: int,
        simulator: Simulator | None = None,
        parent=None,
        theme: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_TITLE)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setMinimumSize(ui_scale.px(_MIN_WIDTH), ui_scale.px(_MIN_HEIGHT))
        self.resize(initial_size(parent, _PARENT_FILL, _SCREEN_FILL))
        self._history = history
        self._positions = record_positions(initial_org, history)
        self._simulator = simulator
        # The position cursor: 0 is the original organisation, len(history)
        # the position after the latest move, where the dialog opens.
        self._position = len(history)
        self._syncing = False
        self._entered = False
        palette = PALETTES[theme if theme is not None else DEFAULT_THEME]
        self._earlier_brush = QBrush(QColor(palette.text_muted))
        layout = QVBoxLayout(self)
        # The identity banner: the glowing mark that opened the dialog
        # beside the accent title, shared with the provenance page.
        layout.addLayout(banner_row(find_about_png(), _TITLE))

        if not history:
            empty = QLabel(_EMPTY_TEXT)
            empty.setObjectName("Muted")
            layout.addWidget(empty)
            layout.addStretch()
            layout.addLayout(self._close_row())
            return

        self._list = QListWidget()
        # Row r shows position r: the original organisation first, then the
        # position each move produced, so the list IS the timeline.
        origin = QListWidgetItem(_ORIGINAL_ROW)
        origin.setForeground(self._earlier_brush)
        self._list.addItem(origin)
        for index, move in enumerate(history):
            label = f"{index + 1}. {move.display_label()}"
            if index < prior_count:
                label = f"{label}{_EARLIER_SUFFIX}"
            item = QListWidgetItem(label)
            if index < prior_count:
                item.setForeground(self._earlier_brush)
            self._list.addItem(item)
        self._list.currentRowChanged.connect(self._on_row_changed)

        map_pane = QWidget()
        map_column = QVBoxLayout(map_pane)
        map_column.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self._caption = QLabel("")
        self._caption.setObjectName("Heading")
        header.addWidget(self._caption)
        header.addStretch()
        self._earlier = self._arrow_button(_EARLIER_GLYPH, _EARLIER_TIP, -1)
        header.addWidget(self._earlier)
        self._later = self._arrow_button(_LATER_GLYPH, _LATER_TIP, 1)
        header.addWidget(self._later)
        map_column.addLayout(header)
        # What the move concretely changed, stated in numbers: always
        # visible, whatever the map's encoding can or cannot show.
        self._change = QLabel("")
        self._change.setObjectName("Muted")
        self._change.setWordWrap(True)
        map_column.addWidget(self._change)
        # Display-only: nothing listens for a drill here, so no open cue.
        self._view = CompleteMapView(drillable=False)
        map_column.addWidget(self._view, 1)
        # The record joins the self-reading family: a long move list and a
        # picture taller than its pane read themselves down at the standard
        # pace; the scroller only acts once content overflows, so attaching
        # it to a record that fits is free.
        self._list_scroller = AutoScroller(self._list)
        self._map_scroller = AutoScroller(self._view)

        panes = QSplitter(Qt.Orientation.Horizontal)
        panes.addWidget(self._list)
        panes.addWidget(map_pane)
        panes.setStretchFactor(0, _LIST_SHARE)
        panes.setStretchFactor(1, _MAP_SHARE)
        panes.setSizes([ui_scale.px(_LIST_PANE_W), ui_scale.px(_MAP_PANE_W)])
        layout.addWidget(panes, 1)
        layout.addLayout(self._close_row())
        # The dialog's explicit focus ring: the list is one stop keeping its
        # own Up and Down; Tab and Right step forward, Shift+Tab and Left
        # back, wrapping; dead arrows (at either end of the timeline) are
        # skipped rather than stalled on.
        self._focus_ring = DialogFocusRing(self, self._ring, self._list_owns_updown)
        self.finished.connect(lambda _result: self._focus_ring.detach())
        self._render_position()

    def _arrow_button(self, glyph: str, tip: str, delta: int) -> QPushButton:
        button = QPushButton(glyph)
        button.setObjectName("RecordArrow")
        button.setToolTip(tip)
        # No autoDefault: Enter belongs to the FOCUSED control (the dialog's
        # keyPressEvent clicks it), never to whichever button Qt made the
        # dialog default.
        button.setAutoDefault(False)
        button.clicked.connect(lambda: self._go(self._position + delta))
        return button

    def _close_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.setAutoDefault(False)
        close_button.clicked.connect(self.accept)
        self._close = close_button
        row.addStretch()
        row.addWidget(close_button)
        return row

    def _ring(self) -> list:
        if not self._history:
            return [(WIDGET_STOP, self._close)]
        return [
            (WIDGET_STOP, self._list),
            (WIDGET_STOP, self._earlier),
            (WIDGET_STOP, self._later),
            (WIDGET_STOP, self._close),
        ]

    def _list_owns_updown(self, widget) -> bool:
        return self._history and (
            widget is self._list or self._list.isAncestorOf(widget)
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # First-stop entry: the dialog opens with the record list focused,
        # so Up and Down walk the moves with no Tab press needed.
        if not self._entered and self._history:
            self._entered = True
            self._list.setFocus(Qt.FocusReason.TabFocusReason)

    def keyPressEvent(self, event) -> None:
        # Enter activates the focused control, exactly as Space does.
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            target = self.focusWidget()
            if isinstance(target, QPushButton) and target.isEnabled():
                target.click()
                return
        super().keyPressEvent(event)

    def _on_row_changed(self, row: int) -> None:
        """Row r IS position r: the origin first, then each move's result."""
        if not self._syncing and row >= 0:
            self._go(row)

    def _go(self, position: int) -> None:
        self._position = max(0, min(position, len(self._history)))
        self._render_position()

    def _sync_list(self) -> None:
        """Follow the cursor in the list without re-entering _go."""
        self._syncing = True
        self._list.setCurrentRow(self._position)
        self._syncing = False

    def _render_position(self) -> None:
        p = self._position
        shown = self._positions[p]
        self._view.set_org(shown)
        self._earlier.setEnabled(p > 0)
        self._later.setEnabled(p < len(self._history))
        self._sync_list()
        # Each line keeps to one frame: the caption describes the POSITION on
        # screen (its own health, so stepping visibly changes the number) and
        # the change line describes the MOVE that produced it (its climb and
        # its located delta), never mixing the two.
        caption = _ORIGINAL_CAPTION if p == 0 else f"Position after move {p}"
        if self._simulator is not None:
            health = self._simulator.score(shown).value
            caption = f"{caption}   ·   structural health {health:.{SCORE_DECIMALS}f}"
        self._caption.setText(caption)
        if p == 0:
            self._view.set_highlight(())
            self._change.setText(_ORIGINAL_CHANGE)
            return
        # Mark where the move that produced this position acted, so a change
        # the border encoding cannot show still has a visible location.
        self._view.set_highlight(self._history[p - 1].targets)
        change = describe_position_change(self._positions[p - 1], self._positions[p])
        if self._simulator is not None:
            before = self._simulator.score(self._positions[p - 1]).value
            after = self._simulator.score(self._positions[p]).value
            change = (
                f"structural health {before:.{SCORE_DECIMALS}f} → "
                f"{after:.{SCORE_DECIMALS}f}; {change}"
            )
        self._change.setText(f"This move changed: {change}")
