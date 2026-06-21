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
from fulcrum.domain.hierarchy import (
    AGGREGATE_MOVE_KINDS,
    child_domains,
    focused_suborg,
)
from fulcrum.domain.models import OrgState
from fulcrum.domain.signals import SignalReading, compute_signals

_EMPTY_SCORE = 0.0


@dataclass(frozen=True, slots=True)
class ScopeAnalysis:
    """The scored picture of one scope; empty when it is too large to play.

    `active` is the section the moves were enumerated on (a leaf's real teams, or
    a non-leaf's rolled-up child nodes), so a caller can name an aggregate move by
    its child domains rather than against the real org where they are not teams.
    """

    playable: bool
    score: float
    signals: tuple[SignalReading, ...]
    valuations: tuple[MoveValuation, ...]
    active: OrgState


def active_org(org: OrgState, focus_id: str | None) -> OrgState:
    """The org actually scored: a focused section, or the whole org."""
    if focus_id is None:
        return org
    return focused_suborg(org, focus_id)


def scope_moves(org: OrgState, focus_id: str | None, active: OrgState):
    """The candidate moves for a scope: at an aggregate scope, only the kinds
    that translate cleanly down to its teams."""
    moves = enumerate_moves(active)
    if focus_id is not None and child_domains(org, focus_id):
        return tuple(m for m in moves if m.kind in AGGREGATE_MOVE_KINDS)
    return moves


def analyze_scope(
    org: OrgState, focus_id: str | None, simulator: Simulator
) -> ScopeAnalysis:
    """Score a scope, or report it unplayable when it is too large to score live."""
    active = active_org(org, focus_id)
    if len(active.teams) > MAX_PLAYABLE_TEAMS:
        return ScopeAnalysis(False, _EMPTY_SCORE, (), (), active)
    return ScopeAnalysis(
        True,
        simulator.score(active).value,
        compute_signals(active),
        simulator.valuate_moves(active, scope_moves(org, focus_id, active)),
        active,
    )
