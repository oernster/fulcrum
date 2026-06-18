"""A large, navigable overview of the whole organisation as a map."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from fulcrum.domain.models import OrgState
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.org_map_view import OrgMapView

_TITLE = "Organisation overview"
_HINT = "Drag to pan, scroll to zoom, double-click a domain to drill in."
_WIDTH = 900
_HEIGHT = 640


class OrgOverviewDialog(QDialog):
    """Shows the whole organisation in a large, navigable map."""

    def __init__(self, org: OrgState, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_TITLE)
        self.resize(ui_scale.px(_WIDTH), ui_scale.px(_HEIGHT))
        layout = QVBoxLayout(self)
        hint = QLabel(_HINT)
        hint.setObjectName("Muted")
        layout.addWidget(hint)
        self._map = OrgMapView()
        layout.addWidget(self._map, 1)
        self._map.set_org(org)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Fit once the dialog is shown so the map frames itself to the real
        # viewport size rather than the pre-layout default.
        QTimer.singleShot(0, self._map.fit_to_contents)
