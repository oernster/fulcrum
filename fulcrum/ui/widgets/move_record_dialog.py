"""The move record: every move to date, with the position before and after.

The exportable HTML presentation's live sibling: the whole record (earlier
runs included) as a list, and for the selected move the complete picture of
the organisation it acted on, toggling between the position before the move
and the position after it.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QBrush, QColor, QGuiApplication
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
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move
from fulcrum.shared.text import SCORE_DECIMALS
from fulcrum.ui import ui_scale
from fulcrum.ui.theme_palettes import DEFAULT_THEME, PALETTES
from fulcrum.ui.widgets.complete_map_view import CompleteMapView
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
_SHOW_BEFORE = "Show the position before this move"
_SHOW_AFTER = "Show the position after this move"
_BEFORE_WORD = "before"
_AFTER_WORD = "after"


class MoveRecordDialog(NeutralDialog):
    """Lists the whole record; the selected move shows before and after."""

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
        self.resize(self._initial_size(parent))
        self._history = history
        self._positions = record_positions(initial_org, history)
        self._simulator = simulator
        self._showing_after = True
        palette = PALETTES[theme if theme is not None else DEFAULT_THEME]
        self._earlier_brush = QBrush(QColor(palette.text_muted))
        layout = QVBoxLayout(self)

        if not history:
            empty = QLabel(_EMPTY_TEXT)
            empty.setObjectName("Muted")
            layout.addWidget(empty)
            layout.addStretch()
            layout.addLayout(self._close_row())
            return

        self._list = QListWidget()
        for index, move in enumerate(history):
            label = f"{index + 1}. {move.display_label()}"
            if index < prior_count:
                label = f"{label}{_EARLIER_SUFFIX}"
            item = QListWidgetItem(label)
            if index < prior_count:
                item.setForeground(self._earlier_brush)
            self._list.addItem(item)
        self._list.currentRowChanged.connect(lambda _row: self._render_selected())

        map_pane = QWidget()
        map_column = QVBoxLayout(map_pane)
        map_column.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self._caption = QLabel("")
        self._caption.setObjectName("Heading")
        header.addWidget(self._caption)
        header.addStretch()
        self._toggle = QPushButton()
        self._toggle.clicked.connect(self._flip)
        header.addWidget(self._toggle)
        map_column.addLayout(header)
        # Display-only: nothing listens for a drill here, so no open cue.
        self._view = CompleteMapView(drillable=False)
        map_column.addWidget(self._view, 1)

        panes = QSplitter(Qt.Orientation.Horizontal)
        panes.addWidget(self._list)
        panes.addWidget(map_pane)
        panes.setStretchFactor(0, _LIST_SHARE)
        panes.setStretchFactor(1, _MAP_SHARE)
        panes.setSizes([ui_scale.px(_LIST_PANE_W), ui_scale.px(_MAP_PANE_W)])
        layout.addWidget(panes, 1)
        layout.addLayout(self._close_row())
        self._list.setCurrentRow(len(history) - 1)

    def _close_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        row.addStretch()
        row.addWidget(close_button)
        return row

    @staticmethod
    def _initial_size(parent) -> QSize:
        """Most of the app window's size, or the screen's when parentless."""
        if parent is not None:
            base = parent.window().size()
            return QSize(
                round(base.width() * _PARENT_FILL),
                round(base.height() * _PARENT_FILL),
            )
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry().size()
        return QSize(
            round(available.width() * _SCREEN_FILL),
            round(available.height() * _SCREEN_FILL),
        )

    def _flip(self) -> None:
        self._showing_after = not self._showing_after
        self._render_selected()

    def _render_selected(self) -> None:
        index = self._list.currentRow()
        if index < 0:
            return
        shown = self._positions[index + 1 if self._showing_after else index]
        self._view.set_org(shown)
        # Mark where the selected move acted, in both positions, so a change
        # the border encoding cannot show still has a visible location.
        self._view.set_highlight(self._history[index].targets)
        # The toggle names the ACTION a press performs, never the state.
        self._toggle.setText(_SHOW_BEFORE if self._showing_after else _SHOW_AFTER)
        word = _AFTER_WORD if self._showing_after else _BEFORE_WORD
        caption = f"Position {word} move {index + 1}"
        if self._simulator is not None:
            before = self._simulator.score(self._positions[index]).value
            after = self._simulator.score(self._positions[index + 1]).value
            caption = (
                f"{caption}   ·   structural health "
                f"{before:.{SCORE_DECIMALS}f} → {after:.{SCORE_DECIMALS}f}"
            )
        self._caption.setText(caption)
