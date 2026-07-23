"""Plan file actions: import the JSON source, export the report and the JSON.

Split from the main window so each module stays within the structural line
limit; the window wires its menu entries to these methods.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QFileDialog, QMessageBox

from fulcrum.application.dto import Plan
from fulcrum.application.game_session import GameSession
from fulcrum.application.interfaces import Clock, PlanExporter, Simulator
from fulcrum.application.plan import build_plan_report
from fulcrum.domain.errors import FulcrumError

_HTML_FILTER = "Presentation (*.html);;All files (*)"
_PLAN_FILTER = "Plan JSON (*.json);;All files (*)"
_DEFAULT_HTML_EXPORT = "fulcrum-presentation.html"
_DEFAULT_JSON_EXPORT = "fulcrum-plan.json"


def downloads_dir() -> str:
    """The user's Downloads folder on any OS, falling back to home."""
    downloads = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DownloadLocation
    )
    return downloads or QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.HomeLocation
    )


def _download_path(filename: str) -> str:
    """A default save path for filename inside the Downloads folder."""
    return str(Path(downloads_dir()) / filename)


class PlanFileActions:
    """Owns the import and export dialogs and their file round-trips."""

    def __init__(
        self,
        window,
        simulator: Simulator,
        plan_exporter: PlanExporter,
        clock: Clock,
        session_of,
        set_session,
    ) -> None:
        self._window = window
        self._simulator = simulator
        self._plan_exporter = plan_exporter
        self._clock = clock
        self._session_of = session_of
        self._set_session = set_session

    def import_plan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self._window, "Import", downloads_dir(), _PLAN_FILTER
        )
        if not path:
            return
        try:
            plan = self._plan_exporter.read(path)
        except (OSError, ValueError, KeyError, FulcrumError) as error:
            QMessageBox.warning(self._window, "Could not open plan", str(error))
            return
        session = GameSession(plan.initial_org, self._simulator)
        for move in plan.moves:
            session.play(move)
        self._set_session(session)

    def export_html(self) -> None:
        session = self._session_of()
        if session is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Create presentation",
            _download_path(_DEFAULT_HTML_EXPORT),
            _HTML_FILTER,
        )
        if not path:
            return
        created = self._clock.timestamp()
        report = build_plan_report(
            session.initial_org, session.history, self._simulator
        )
        self._plan_exporter.export_html(
            path, report, session.initial_org, session.org, created
        )
        QMessageBox.information(
            self._window,
            "Presentation created",
            "Wrote the HTML presentation you can share.",
        )

    def export_json(self) -> None:
        session = self._session_of()
        if session is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self._window, "Export", _download_path(_DEFAULT_JSON_EXPORT), _PLAN_FILTER
        )
        if not path:
            return
        created = self._clock.timestamp()
        plan = Plan(session.initial_org, session.history, created)
        self._plan_exporter.export_json(path, plan)
        QMessageBox.information(
            self._window, "Plan exported", "Wrote the JSON plan you can re-import."
        )
