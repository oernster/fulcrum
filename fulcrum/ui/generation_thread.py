"""Generate a random organisation on a worker thread, off the UI thread.

Generation is a pure but sometimes heavy computation: a large band builds a state
of tens of thousands of teams. Running it here on a QThread and delivering the
finished OrgState back through a queued signal keeps the Qt event loop free, so
the window stays responsive while the organisation is built rather than freezing.
"""

from __future__ import annotations

from random import Random

from PySide6.QtCore import QThread, Signal

from fulcrum.application.level_generator import generate_level
from fulcrum.domain.org_size import OrgSizeBand


class GenerationThread(QThread):
    """Runs generate_level off the UI thread and emits the finished org."""

    generated = Signal(object)

    def __init__(self, rng: Random, band: OrgSizeBand, parent=None) -> None:
        super().__init__(parent)
        self._rng = rng
        self._band = band

    def run(self) -> None:
        self.generated.emit(generate_level(self._rng, self._band))
