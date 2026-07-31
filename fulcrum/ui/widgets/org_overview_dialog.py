"""A large overview of the whole organisation.

It offers two ways to see the org: a complete picture (every domain, sub-domain
and team at once) and the navigable drill-down map, switched from a toggle
button whose icon and label show the current mode (its tooltip names the
switch, so the control reads as the mode indicator it is).
"""

from __future__ import annotations

from PySide6.QtCore import QSize, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
)

from fulcrum.domain.hierarchy import total_headcount
from fulcrum.domain.models import OrgState
from fulcrum.shared.text import count_noun
from fulcrum.ui import ui_scale
from fulcrum.ui.icons import button_icon
from fulcrum.ui.widgets.complete_map_view import CompleteMapView
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog
from fulcrum.ui.widgets.org_map_view import OrgMapView

_TITLE = "Organisation overview"
_COMPLETE = "Complete picture"
_DRILL = "Drill down"
_COMPLETE_HINT = "The whole organisation at full size. Drag to pan, scroll to zoom."
_DRILL_HINT = "Drag to pan, scroll to zoom, click a domain to drill in."
_COMPLETE_ICON = "view_complete"
_DRILL_ICON = "view_drill"
_SWITCH_TO_DRILL = "Switch to the drill-down map"
_SWITCH_TO_COMPLETE = "Switch to the complete picture"
_TOGGLE_ICON_PX = 22
_WIDTH = 980
_HEIGHT = 680
_COMPLETE_INDEX = 0
_DRILL_INDEX = 1


class OrgOverviewDialog(NeutralDialog):
    """Shows the whole organisation, as a complete picture or a drill-down map."""

    def __init__(self, org: OrgState, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_TITLE)
        self.resize(ui_scale.px(_WIDTH), ui_scale.px(_HEIGHT))
        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self._mode = QPushButton()
        self._mode.setIconSize(
            QSize(ui_scale.px(_TOGGLE_ICON_PX), ui_scale.px(_TOGGLE_ICON_PX))
        )
        self._mode.clicked.connect(self._toggle)
        controls.addWidget(self._mode)
        controls.addStretch()
        summary = QLabel(
            f"{count_noun(total_headcount(org), 'person', 'people')} · "
            f"{count_noun(len(org.teams), 'team')}"
        )
        summary.setObjectName("Heading")
        controls.addWidget(summary)
        layout.addLayout(controls)

        self._hint = QLabel(_COMPLETE_HINT)
        self._hint.setObjectName("Muted")
        layout.addWidget(self._hint)

        self._stack = QStackedWidget()
        self._complete = CompleteMapView()
        self._drill = OrgMapView()
        self._stack.addWidget(self._complete)
        self._stack.addWidget(self._drill)
        layout.addWidget(self._stack, 1)

        self._complete.set_org(org)
        self._drill.set_org(org)
        self._apply_mode()

    def _toggle(self) -> None:
        self._stack.setCurrentIndex(
            _DRILL_INDEX
            if self._stack.currentIndex() == _COMPLETE_INDEX
            else _COMPLETE_INDEX
        )
        self._apply_mode()
        self._fit_current()

    def _apply_mode(self) -> None:
        """Dress the toggle as the current mode; the tooltip names the switch."""
        complete = self._stack.currentIndex() == _COMPLETE_INDEX
        self._mode.setIcon(button_icon(_COMPLETE_ICON if complete else _DRILL_ICON))
        self._mode.setText(_COMPLETE if complete else _DRILL)
        self._mode.setToolTip(_SWITCH_TO_DRILL if complete else _SWITCH_TO_COMPLETE)
        self._hint.setText(_COMPLETE_HINT if complete else _DRILL_HINT)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Fit once shown so each map frames itself to the real viewport size.
        QTimer.singleShot(0, self._fit_current)

    def _fit_current(self) -> None:
        current = self._stack.currentWidget()
        if current is self._complete:
            self._complete.show_full_size()
        else:
            current.fit_to_contents()
