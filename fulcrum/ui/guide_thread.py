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
    """Runs build_org_guide twice (fixed, grown) and emits the pair.

    progress reports (sections planned, total sections) across BOTH passes:
    the two passes plan the same frames, so the fixed pass covers the first
    half of the bar and the grown pass the second.
    """

    built = Signal(object)
    progress = Signal(int, int)

    _PASSES = 2

    def __init__(self, org: OrgState, simulator: Simulator, parent=None) -> None:
        super().__init__(parent)
        self._org = org
        self._simulator = simulator

    def run(self) -> None:
        fixed = build_org_guide(self._org, self._simulator, progress=self._first)
        grown = build_org_guide(
            self._org, self._simulator, allow_growth=True, progress=self._second
        )
        self.built.emit((fixed, grown))

    def _first(self, done: int, total: int) -> None:
        self.progress.emit(done, total * self._PASSES)

    def _second(self, done: int, total: int) -> None:
        self.progress.emit(total + done, total * self._PASSES)
