"""Boundary Protocols implemented by the infrastructure layer and by test fakes.

These are structural seams. The simulator Protocol in particular lets the hot
path move to a faster kernel later without touching the domain or the UI.
"""

from __future__ import annotations

from typing import Protocol

from fulcrum.application.dto import (
    MoveValuation,
    OrgBlueprint,
    Plan,
    PlanReport,
    SavedGame,
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


class Clock(Protocol):
    """A wall-clock source, injected so the rest of the app stays testable."""

    def timestamp(self) -> str: ...


class SaveGameRepository(Protocol):
    """Persists and restores saved games by slot name."""

    def save(self, slot: str, game: SavedGame) -> None: ...

    def load(self, slot: str) -> SavedGame: ...

    def slots(self) -> tuple[str, ...]: ...


class OrgImporter(Protocol):
    """Builds an org blueprint from an external source path."""

    def import_org(self, path: str) -> OrgBlueprint: ...


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
