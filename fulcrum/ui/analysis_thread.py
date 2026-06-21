"""Score a scope on a worker thread so the board never blocks while drilling.

Each refresh starts one of these with a request id; the board renders only the
result whose id is still current, so a flurry of drills resolves to the latest
section rather than racing. Building and scoring the section happens here, off
the UI thread, however large it is.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from fulcrum.application.interfaces import Simulator
from fulcrum.application.scope_analysis import analyze_scope
from fulcrum.domain.models import OrgState


class AnalysisThread(QThread):
    """Runs analyze_scope off the UI thread, emitting (request id, result)."""

    analysed = Signal(int, object)

    def __init__(
        self,
        request: int,
        org: OrgState,
        focus_id: str | None,
        simulator: Simulator,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._request = request
        self._org = org
        self._focus_id = focus_id
        self._simulator = simulator

    def run(self) -> None:
        result = analyze_scope(self._org, self._focus_id, self._simulator)
        self.analysed.emit(self._request, result)
