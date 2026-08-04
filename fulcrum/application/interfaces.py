"""Boundary Protocols implemented by the infrastructure layer and by test fakes.

These are structural seams. The simulator Protocol in particular lets the hot
path move to a faster kernel later without touching the domain or the UI.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from fulcrum.application.dto import (
    ExampleSummary,
    MoveValuation,
    Plan,
    PlanReport,
    SessionSnapshot,
)
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move
from fulcrum.domain.simulation import StructuralScore


class Simulator(Protocol):
    """Scores org states and valuates candidate moves."""

    def score(self, org: OrgState) -> StructuralScore: ...

    def valuate_moves(
        self, org: OrgState, moves: tuple[Move, ...]
    ) -> tuple[MoveValuation, ...]: ...


class GuideWorkerPool(Protocol):
    """Prices the guide's independent workloads on worker processes.

    An implementation must be bit-identical to the serial loop it stands
    in for: the same values in the same order, with only the wall-clock
    differing, so the guide's published numbers never depend on whether
    a pool was available. cancelled, when given, is consulted while
    waiting on workers, so a cancellation request is honoured promptly
    even before any task has completed.
    """

    def price_lines(
        self,
        simulator: Simulator,
        org: OrgState,
        full: float,
        line_moves: tuple[tuple[Move, ...], ...],
        progress: Callable[[], None] | None,
        cancelled: Callable[[], bool] | None = None,
    ) -> tuple[float, ...]: ...

    def valuate_moves(
        self,
        simulator: Simulator,
        org: OrgState,
        moves: tuple[Move, ...],
        progress: Callable[[int], None] | None,
        cancelled: Callable[[], bool] | None = None,
    ) -> tuple[MoveValuation, ...]: ...


class Clock(Protocol):
    """A wall-clock source, injected so the rest of the app stays testable."""

    def timestamp(self) -> str: ...


class OrgStore(Protocol):
    """Persists the session (org plus move history) across app runs.

    A store that cannot read what it finds must not destroy it. ``load``
    returning None therefore has two meanings the caller has to tell apart:
    nothing was saved, or something was saved and could not be read. The two
    members below report the second case, so a failed restore can be said out
    loud rather than silently replaced by a fresh session.
    """

    def save(self, snapshot: SessionSnapshot) -> None: ...

    def load(self) -> SessionSnapshot | None: ...

    @property
    def preserved_copy(self) -> Path | None: ...

    @property
    def is_sealed(self) -> bool: ...


class SettingsStore(Protocol):
    """Persists small user preferences (the theme) across app runs."""

    def load_theme(self) -> str: ...

    def save_theme(self, theme: str) -> None: ...


class ExampleSource(Protocol):
    """Lists the bundled example organisations and loads one by key."""

    def examples(self) -> tuple[ExampleSummary, ...]: ...

    def load(self, key: str) -> OrgState: ...


class PlanExporter(Protocol):
    """Writes a plan's HTML report and its JSON source as separate exports."""

    def export_html(
        self,
        path: str,
        report: PlanReport,
        initial_org: OrgState,
        final_org: OrgState,
        created_at: str,
    ) -> None: ...

    def export_json(self, path: str, plan: Plan) -> None: ...

    def read(self, path: str) -> Plan: ...
