"""Build one hierarchy guide on a worker thread, off the UI thread.

Planning every frame of a large organisation is minutes of small planner
runs plus the composition guard; a QThread keeps the event loop free. The
guide dialog opens on the fixed guide alone and the grown variant is built
lazily by a second run, only when the grow toggle first asks for it, so
nobody pays for growth they never look at.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from fulcrum.application.interfaces import Simulator
from fulcrum.application.org_guide import build_org_guide
from fulcrum.domain.models import OrgState


class OrgGuideThread(QThread):
    """Runs build_org_guide once and emits the finished guide.

    progress forwards the builder's (work done, total work) reports; the
    total is declared once, up front, from reserves bounding the guard
    and growth phases, so the fraction climbs monotonically and the
    build's final snap closes the bar.
    """

    built = Signal(object)
    progress = Signal(int, int)

    def __init__(
        self,
        org: OrgState,
        simulator: Simulator,
        allow_growth: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._org = org
        self._simulator = simulator
        self._allow_growth = allow_growth

    def run(self) -> None:
        guide = build_org_guide(
            self._org,
            self._simulator,
            allow_growth=self._allow_growth,
            progress=self.progress.emit,
        )
        self.built.emit(guide)
