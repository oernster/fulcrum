"""Build the whole-hierarchy guide on a worker thread, off the UI thread.

Planning every frame of a large organisation is many small planner runs; a
QThread keeps the event loop free and delivers both variants (fixed size and
allowed to grow) in one pass, so the dialog's grow toggle swaps instantly.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from fulcrum.application.interfaces import Simulator
from fulcrum.application.org_guide import build_org_guide
from fulcrum.domain.models import OrgState


class OrgGuideThread(QThread):
    """Runs build_org_guide twice (fixed, grown) and emits the pair."""

    built = Signal(object)

    def __init__(self, org: OrgState, simulator: Simulator, parent=None) -> None:
        super().__init__(parent)
        self._org = org
        self._simulator = simulator

    def run(self) -> None:
        fixed = build_org_guide(self._org, self._simulator)
        grown = build_org_guide(self._org, self._simulator, allow_growth=True)
        self.built.emit((fixed, grown))
