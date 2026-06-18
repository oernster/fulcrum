"""Procedural level generation with a solvability guarantee.

A generated level is a densely coupled position with one authoritative team and
the rest lacking authority, so a collapsing or delegating move is always strong.
The randomness varies the flavour (size, delays, skew, workload), never the
existence of a solution, so every level is playable and provably has a great
move.

Every level is grouped into domains, and larger ones nest a sub-domain, so a
generated org always reads as a real structure rather than a flat team list and
exercises the hierarchy, the navigable map and the per-domain plan. The grouping
is navigational metadata over the same teams, so it never changes the score or
the guaranteed great move.
"""

from __future__ import annotations

from random import Random

from fulcrum.application.game_session import enumerate_moves
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import (
    GROUP_CATEGORIES,
    Dependency,
    Domain,
    Origin,
    OrgState,
    Team,
)
from fulcrum.domain.moves import apply_move
from fulcrum.domain.simulation import MoveClassification

_TEAM_CHOICES: tuple[int, ...] = (4, 5, 6, 7, 8, 9, 10)
_LOOKAHEAD: int = 10
_MIN_DELAY: int = 3
_MAX_DELAY: int = 6
_MIN_WORKLOAD: int = 6
_MAX_WORKLOAD: int = 9
_MIN_SKEW: float = 0.3
_MAX_SKEW: float = 0.9
_SKEW_DECIMALS: int = 2

# Every generated org is grouped into root domains, so a level always reads as a
# real structure rather than a flat team list; at or above the sub-domain
# threshold one domain is nested under the first, making it two levels deep. The
# grouping is metadata only and never changes the score.
_SUBDOMAIN_THRESHOLD: int = 5
_ROOT_DOMAINS: int = 2
_ROOT_CATEGORY: str = GROUP_CATEGORIES[0]
_SUB_CATEGORY: str = GROUP_CATEGORIES[1]

# Cosmetic name pools for generated domains and their leads, the structural
# equivalent of the "Team N" team names: drawn at random, never load-bearing.
_DOMAIN_NAMES: tuple[str, ...] = (
    "Platform",
    "Product",
    "Data",
    "Operations",
    "Security",
    "Growth",
)
_LEAD_NAMES: tuple[str, ...] = (
    "Avery",
    "Bo",
    "Cass",
    "Devi",
    "Esin",
    "Faye",
    "Gabriel",
)


def _build_domains(rng: Random, count: int) -> tuple[tuple[Domain, ...], list[str]]:
    """Return the domains and a per-team domain id for an org of `count` teams.

    Every org is grouped into root domains; from the sub-domain threshold up,
    one extra domain is nested under the first so the org is two levels deep.
    """
    nested = count >= _SUBDOMAIN_THRESHOLD
    total = _ROOT_DOMAINS + (1 if nested else 0)
    names = rng.sample(_DOMAIN_NAMES, total)
    leads = rng.sample(_LEAD_NAMES, total)
    domains = [
        Domain(
            id=f"domain_{k + 1}",
            name=names[k],
            lead=leads[k],
            category=_ROOT_CATEGORY,
        )
        for k in range(_ROOT_DOMAINS)
    ]
    if nested:
        domains.append(
            Domain(
                id=f"domain_{_ROOT_DOMAINS + 1}",
                name=names[_ROOT_DOMAINS],
                parent_id="domain_1",
                lead=leads[_ROOT_DOMAINS],
                category=_SUB_CATEGORY,
            )
        )
    assignable = [domain.id for domain in domains]
    domain_of: list[str | None] = [
        assignable[i % len(assignable)] for i in range(count)
    ]
    return tuple(domains), domain_of


def _random_org(rng: Random) -> OrgState:
    count = rng.choice(_TEAM_CHOICES)
    domains, domain_of = _build_domains(rng, count)
    teams = tuple(
        Team(
            id=f"team_{i + 1}",
            name=f"Team {i + 1}",
            has_local_authority=(i == 0),
            incentive_skew=round(rng.uniform(_MIN_SKEW, _MAX_SKEW), _SKEW_DECIMALS),
            domain_id=domain_of[i],
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
        domains=domains,
    )


def generate_level(rng: Random) -> OrgState:
    """Generate a playable level whose great move is reachable, not immediate.

    Resample until the position can reach a great move along its greedy
    improvement path. Relaxing the old "great move available now" rule lets
    larger, deeper orgs through: their dominant move often only opens up after a
    few setup moves, which is fine for a playable level.
    """
    simulator = DeterministicSimulator()
    while True:
        org = _random_org(rng)
        if _reaches_great_move(org, simulator):
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


def _reaches_great_move(
    org: OrgState, simulator: DeterministicSimulator, lookahead: int = _LOOKAHEAD
) -> bool:
    """Whether a great move is reachable within `lookahead` greedy improvements.

    A great move need not be available now: following the best improving move
    step by step, the position may open one up within a few moves, which is
    enough for a playable level.
    """
    current = org
    for _ in range(lookahead + 1):
        if has_great_move(current, simulator):
            return True
        improving = [
            valuation
            for valuation in simulator.valuate_moves(current, enumerate_moves(current))
            if valuation.delta > 0
        ]
        if not improving:
            return False
        best = max(improving, key=lambda valuation: valuation.delta)
        current = apply_move(current, best.move)
    return False
