"""On-demand, threaded preview of a candidate move on the map.

Previewing a move rebuilds the org and redraws the map. That is too heavy to run
on every hover of a large org (it froze the UI), so it is explicit: the board's
per-move magnifier button toggles it. The rebuild runs on a worker thread, off
the UI thread, and the map is redrawn from the result with the newest request
winning. Toggling the same move again, or navigating away, restores the real
view.

MovePreview is a QObject so the worker's result is delivered to its slot on the
UI thread (a queued cross-thread connection), never touching widgets off-thread.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal

from fulcrum.application.dto import MoveValuation
from fulcrum.domain.hierarchy import translate_focused_move
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import apply_move


class _PreviewWorker(QThread):
    """Rebuilds the post-move org off the UI thread; emits (request, org, move)."""

    ready = Signal(int, object, object)

    def __init__(
        self,
        request: int,
        org: OrgState,
        focus_id: str | None,
        valuation: MoveValuation,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._request = request
        self._org = org
        self._focus_id = focus_id
        self._valuation = valuation

    def run(self) -> None:
        real = translate_focused_move(self._org, self._focus_id, self._valuation.move)
        self.ready.emit(self._request, apply_move(self._org, real), self._valuation)


class MovePreview(QObject):
    """Toggles a threaded map preview of a move, the newest request winning."""

    def __init__(
        self,
        parent: QObject,
        show: Callable[[OrgState, MoveValuation], None],
        restore: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._show = show
        self._restore = restore
        self._request = 0
        self._workers: set[_PreviewWorker] = set()
        self._shown: MoveValuation | None = None

    def toggle(
        self, org: OrgState, focus_id: str | None, valuation: MoveValuation
    ) -> None:
        """Preview the move, or restore the real view if it is already shown."""
        if self._shown == valuation:
            self.reset()
            self._restore()
            return
        self._request += 1
        worker = _PreviewWorker(self._request, org, focus_id, valuation, self)
        worker.ready.connect(self._on_ready)
        worker.finished.connect(lambda w=worker: self._workers.discard(w))
        worker.finished.connect(worker.deleteLater)
        self._workers.add(worker)
        worker.start()

    def reset(self) -> None:
        """Forget the shown preview and ignore any in-flight worker's result."""
        self._request += 1
        self._shown = None

    def _on_ready(
        self, request: int, preview: OrgState, valuation: MoveValuation
    ) -> None:
        if request != self._request:
            return
        self._show(preview, valuation)
        self._shown = valuation
