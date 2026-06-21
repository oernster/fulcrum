"""Compute everything the board shows for one scope, free of any UI thread.

A scope is the whole org or one focused section of it. Building that section and
scoring it (the health score, the signals and every candidate move's value) is
the heavy part of a refresh, and it is pure: it reads an immutable org and a
frozen simulator and returns a value object. The board runs it on a worker
thread and renders the result, so drilling never blocks the UI however large the
section. A section too large to score live is reported unplayable instead, to be
drilled into rather than scored whole.
"""

from __future__ import annotations

from dataclasses import dataclass

from fulcrum.application.dto import MoveValuation
from fulcrum.application.game_session import MAX_PLAYABLE_TEAMS, enumerate_moves
from fulcrum.application.interfaces import Simulator
from fulcrum.domain.hierarchy import focused_suborg
from fulcrum.domain.models import OrgState
from fulcrum.domain.signals import SignalReading, compute_signals

_EMPTY_SCORE = 0.0


@dataclass(frozen=True, slots=True)
class ScopeAnalysis:
    """The scored picture of one scope; empty when it is too large to play."""

    playable: bool
    score: float
    signals: tuple[SignalReading, ...]
    valuations: tuple[MoveValuation, ...]


def active_org(org: OrgState, focus_id: str | None) -> OrgState:
    """The org actually scored: a focused section, or the whole org."""
    if focus_id is None:
        return org
    return focused_suborg(org, focus_id)


def analyze_scope(
    org: OrgState, focus_id: str | None, simulator: Simulator
) -> ScopeAnalysis:
    """Score a scope, or report it unplayable when it is too large to score live."""
    active = active_org(org, focus_id)
    if len(active.teams) > MAX_PLAYABLE_TEAMS:
        return ScopeAnalysis(False, _EMPTY_SCORE, (), ())
    return ScopeAnalysis(
        True,
        simulator.score(active).value,
        compute_signals(active),
        simulator.valuate_moves(active, enumerate_moves(active)),
    )
