"""Builders for the board's move rows, signal chips and a layout reset.

These stay apart from BoardView so the view keeps within the module-size limit.
Each builder takes the callbacks it needs, so it never touches the session.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLayout, QPushButton, QWidget

from fulcrum.application.dto import MoveValuation
from fulcrum.application.move_text import describe_move
from fulcrum.domain.models import OrgState
from fulcrum.domain.signals import SignalReading
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.hover_button import HoverButton

_VALUE_DECIMALS = 1
_PREVIEW_ICON = "🔍"
_PREVIEW_TIP = "Preview this move"
_PREVIEW_BTN_W = 44


def clear_layout(layout: QLayout) -> None:
    """Remove and delete every widget held by a layout, leaving it empty."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def magnifier_button(on_click: Callable[[], None]) -> QPushButton:
    """The preview magnifier, styled and sized as on the board's move rows."""
    button = QPushButton(_PREVIEW_ICON)
    button.setObjectName("PreviewButton")
    button.setToolTip(_PREVIEW_TIP)
    button.setFixedWidth(ui_scale.px(_PREVIEW_BTN_W))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.clicked.connect(lambda _=False: on_click())
    return button


def move_row(
    scope_active: OrgState,
    valuation: MoveValuation,
    on_play: Callable[[MoveValuation], None],
    on_preview: Callable[[MoveValuation], None],
) -> QWidget:
    """A move button plus its preview magnifier, wired to the given callbacks."""
    button = QPushButton(
        f"{describe_move(scope_active, valuation.move)}   "
        f"[{valuation.classification.value}]   "
        f"{valuation.delta:+.{_VALUE_DECIMALS}f}"
    )
    button.setObjectName("MoveButton")
    button.clicked.connect(lambda _=False, v=valuation: on_play(v))
    magnifier = magnifier_button(lambda v=valuation: on_preview(v))
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(button, 1)
    row.addWidget(magnifier)
    holder = QWidget()
    holder.setLayout(row)
    return holder


def signal_chip(
    reading: SignalReading,
    on_enter: Callable[[SignalReading, QWidget], None],
    on_leave: Callable[[], None],
) -> HoverButton:
    """A hover-aware chip for one signal reading, wired to the given callbacks."""
    chip = HoverButton(
        f"{reading.definition.label}: "
        f"{reading.value:.{_VALUE_DECIMALS}f} {reading.definition.unit}"
    )
    chip.setObjectName("SignalChip")
    chip.entered.connect(lambda r=reading, c=chip: on_enter(r, c))
    chip.left.connect(on_leave)
    return chip
