"""A large overview of the whole organisation.

It offers two ways to see the org: a complete picture (every domain, sub-domain
and team at once) and the navigable drill-down map, switched from a selector.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
)

from fulcrum.domain.hierarchy import total_headcount
from fulcrum.domain.models import OrgState
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.complete_map_view import CompleteMapView
from fulcrum.ui.widgets.org_map_view import OrgMapView

_TITLE = "Organisation overview"
_COMPLETE = "Complete picture"
_DRILL = "Drill down"
_COMPLETE_HINT = "The whole organisation at once. Drag to pan, scroll to zoom."
_DRILL_HINT = "Drag to pan, scroll to zoom, click a domain to drill in."
_WIDTH = 980
_HEIGHT = 680
_COMPLETE_INDEX = 0


class OrgOverviewDialog(QDialog):
    """Shows the whole organisation, as a complete picture or a drill-down map."""

    def __init__(self, org: OrgState, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_TITLE)
        self.resize(ui_scale.px(_WIDTH), ui_scale.px(_HEIGHT))
        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self._mode = QComboBox()
        self._mode.addItems([_COMPLETE, _DRILL])
        controls.addWidget(self._mode)
        controls.addStretch()
        summary = QLabel(f"{total_headcount(org):,} people · {len(org.teams)} teams")
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
        self._mode.currentIndexChanged.connect(self._switch)

    def _switch(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        complete = index == _COMPLETE_INDEX
        self._hint.setText(_COMPLETE_HINT if complete else _DRILL_HINT)
        self._fit_current()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Fit once shown so each map frames itself to the real viewport size.
        QTimer.singleShot(0, self._fit_current)

    def _fit_current(self) -> None:
        self._stack.currentWidget().fit_to_contents()
