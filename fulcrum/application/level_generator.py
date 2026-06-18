"""Procedural level generation with a solvability guarantee.

A generated level is a densely coupled position with one authoritative team and
the rest lacking authority, so a collapsing or delegating move is always strong.
The randomness varies the flavour (size, delays, skew, workload), never the
existence of a solution, so every level is playable and provably has a great
move.
"""

from __future__ import annotations

from random import Random

from fulcrum.application.game_session import enumerate_moves
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Dependency, Origin, OrgState, Team
from fulcrum.domain.simulation import MoveClassification

_MIN_TEAMS: int = 3
_MID_TEAMS: int = 4
_MAX_TEAMS: int = 5
_MIN_DELAY: int = 3
_MAX_DELAY: int = 6
_MIN_WORKLOAD: int = 6
_MAX_WORKLOAD: int = 9
_MIN_SKEW: float = 0.3
_MAX_SKEW: float = 0.9
_SKEW_DECIMALS: int = 2


def _random_org(rng: Random) -> OrgState:
    count = rng.choice((_MIN_TEAMS, _MID_TEAMS, _MAX_TEAMS))
    teams = tuple(
        Team(
            id=f"team_{i + 1}",
            name=f"Team {i + 1}",
            has_local_authority=(i == 0),
            incentive_skew=round(rng.uniform(_MIN_SKEW, _MAX_SKEW), _SKEW_DECIMALS),
        )
        for i in range(count)
    )
    dependencies = tuple(
        Dependency(
            f"team_{i + 1}", f"team_{j + 1}", rng.randint(_MIN_DELAY, _MAX_DELAY)
        )
        for i in range(count)
        for j in range(i + 1, count)
    )
    workload = rng.randint(_MIN_WORKLOAD, _MAX_WORKLOAD)
    return OrgState(
        teams=teams,
        dependencies=dependencies,
        workload=workload,
        origin=Origin.GENERATED,
    )


def generate_level(rng: Random) -> OrgState:
    """Generate a playable level that is guaranteed to have a great move.

    Resample until the position has a great move, so a generated level always
    has a dominant answer to find, the way a puzzle generator only ships a
    position once it has verified a solution.
    """
    org = _random_org(rng)
    while not has_great_move(org):
        org = _random_org(rng)
    return org


def has_great_move(
    org: OrgState, simulator: DeterministicSimulator | None = None
) -> bool:
    """Return whether at least one candidate move is classified great."""
    sim = simulator or DeterministicSimulator()
    return any(
        valuation.classification == MoveClassification.GREAT
        for valuation in sim.valuate_moves(org, enumerate_moves(org))
    )
