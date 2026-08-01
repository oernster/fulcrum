"""Owns the hierarchy-guide flow: build off-thread, open, grow lazily.

Split from the main window so it stays within the structural line limit.
The fixed guide builds behind a determinate progress dialog and opens the
guide; the grown variant costs as much again or more, so it is built only
when the dialog's grow toggle first asks, behind its own progress dialog.
Playing a move from the guide rebuilds the fixed guide alone; the dialog
drops its stale grown guide and re-requests it lazily.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication

from fulcrum.application.game_session import GameSession
from fulcrum.application.interfaces import Simulator
from fulcrum.application.org_guide_parallel import build_org_guide_auto
from fulcrum.ui.guide_thread import OrgGuideThread
from fulcrum.ui.widgets.busy_dialog import BusyDialog
from fulcrum.ui.widgets.org_guide_dialog import OrgGuideDialog


class GuideLauncher:
    """Drives guide building and the guide dialog for the main window."""

    def __init__(
        self,
        window,
        simulator: Simulator,
        session_of: Callable[[], GameSession | None],
        on_played: Callable[[], None],
        inform: Callable[[str, str], None],
        theme_of: Callable[[], str],
    ) -> None:
        self._window = window
        self._simulator = simulator
        self._session_of = session_of
        self._on_played = on_played
        self._inform = inform
        self._theme_of = theme_of

    def show(self) -> None:
        """Plan every level off-thread, then open the hierarchy guide."""
        session = self._session_of()
        if session is None:
            return
        self._busy = BusyDialog(
            "Planning every level...",
            self._window,
            determinate=True,
            on_cancel=lambda: self._thread.request_cancel(),
        )
        self._busy.show()
        # Paint the dialog before the worker starts: the planner's tight
        # Python loops hold the GIL, which can starve the first paint for
        # seconds and leave the dialog a blank white rectangle.
        QApplication.processEvents()
        self._thread = OrgGuideThread(session.org, self._simulator)
        self._thread.progress.connect(self._busy.set_progress)
        self._thread.built.connect(self._on_built)
        self._thread.cancelled.connect(self._busy.close)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_built(self, guide) -> None:
        self._busy.close()
        OrgGuideDialog(
            guide,
            self._simulator,
            self._play,
            self._window,
            self._theme_of(),
            grow_planner=self._plan_growth_for,
        ).exec()

    def _plan_growth_for(self, dialog) -> None:
        """Build the grown guide for the open dialog, off-thread with a bar."""
        session = self._session_of()
        if session is None:
            return
        self._growth_busy = BusyDialog(
            "Planning growth...",
            dialog,
            determinate=True,
            on_cancel=lambda: self._growth_thread.request_cancel(),
        )
        self._growth_busy.show()
        QApplication.processEvents()
        self._growth_thread = OrgGuideThread(
            session.org, self._simulator, allow_growth=True
        )
        self._growth_thread.progress.connect(self._growth_busy.set_progress)
        self._growth_thread.built.connect(
            lambda guide, d=dialog: self._on_growth_built(d, guide)
        )
        self._growth_thread.cancelled.connect(
            lambda d=dialog: self._on_growth_cancelled(d)
        )
        self._growth_thread.finished.connect(self._growth_thread.deleteLater)
        self._growth_thread.start()

    def _on_growth_cancelled(self, dialog) -> None:
        """A cancelled grown build: close the bar and release the toggle."""
        self._growth_busy.close()
        dialog.growth_cancelled()

    def _on_growth_built(self, dialog, guide) -> None:
        self._growth_busy.close()
        dialog.set_growth_guide(guide)

    def _play(self, move, frame_id):
        """Play a guide move live; return the refreshed fixed guide, or None."""
        session = self._session_of()
        if session is None:
            return None
        if not session.try_play_in_frame(move, frame_id):
            self._inform(
                "Cannot play this move yet",
                "This move builds on earlier moves in the path; play those first.",
            )
            return None
        self._on_played()
        return build_org_guide_auto(session.org, self._simulator)
