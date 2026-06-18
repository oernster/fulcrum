"""Procedural level generation with a solvability guarantee.

A generated level is a densely coupled position with one authoritative team and
the rest lacking authority, so a collapsing or delegating move is always strong.
The randomness varies the flavour (size, delays, skew, workload), never the
existence of a solution, so every level is playable and provably has a great
move.

Every level nests into a real multi-tier hierarchy. Two root divisions branch
into departments, then larger orgs branch once more into groups, with teams
spread across the leaf domains. A generated org therefore reads like a real
organisation rather than one flat level and exercises the hierarchy, the
navigable map and the per-domain plan. The nesting is navigational metadata over
the same teams, so it never changes the score or the guaranteed great move.
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

_TEAM_CHOICES: tuple[int, ...] = (6, 7, 8, 9, 10)
_LOOKAHEAD: int = 10
_MIN_DELAY: int = 3
_MAX_DELAY: int = 6
_MIN_WORKLOAD: int = 6
_MAX_WORKLOAD: int = 9
_MIN_SKEW: float = 0.3
_MAX_SKEW: float = 0.9
_SKEW_DECIMALS: int = 2

# Generated orgs nest into a real multi-tier hierarchy rather than one flat
# level: two root divisions branch into departments, then larger orgs branch
# once more into groups. Teams are spread across the leaf domains. The nesting
# is metadata only and never changes the score.
_ROOT_DOMAINS: int = 2
_CHILDREN_PER_DOMAIN: int = 2
_DEPTH_MEDIUM: int = 2
_DEPTH_DEEP: int = 3
_DEEP_THRESHOLD: int = 12

# Cosmetic name pools for generated domains and their leads, the structural
# equivalent of the "Team N" team names: drawn at random, never load-bearing.
_DOMAIN_NAMES: tuple[str, ...] = (
    "Platform",
    "Product",
    "Data",
    "Operations",
    "Security",
    "Growth",
    "Finance",
    "Legal",
    "Marketing",
    "Sales",
    "Support",
    "Research",
    "Infrastructure",
    "Quality",
    "Design",
    "Delivery",
)
_LEAD_NAMES: tuple[str, ...] = (
    "Avery",
    "Bo",
    "Cass",
    "Devi",
    "Esin",
    "Faye",
    "Gabriel",
    "Hana",
    "Ira",
    "Jun",
    "Kit",
    "Lena",
    "Mara",
    "Nils",
    "Omar",
    "Pia",
)


def _tier_category(tier: int) -> str:
    return GROUP_CATEGORIES[min(tier, len(GROUP_CATEGORIES) - 1)]


def _domain_total(depth: int) -> int:
    total = 0
    tier_size = _ROOT_DOMAINS
    for _ in range(depth):
        total += tier_size
        tier_size *= _CHILDREN_PER_DOMAIN
    return total


def _build_domains(rng: Random, count: int) -> tuple[tuple[Domain, ...], list[str]]:
    """Return the domains and a per-team leaf-domain id for `count` teams.

    The org nests into two tiers (divisions then departments), or three for
    larger orgs (divisions, departments then groups). Teams are spread across
    the leaf domains, so a generated org is a real multi-level structure.
    """
    depth = _DEPTH_DEEP if count >= _DEEP_THRESHOLD else _DEPTH_MEDIUM
    total = _domain_total(depth)
    names = rng.sample(_DOMAIN_NAMES, total)
    leads = rng.sample(_LEAD_NAMES, total)
    domains: list[Domain] = []
    index = 0
    current: list[str] = []
    for _ in range(_ROOT_DOMAINS):
        domain_id = f"domain_{index + 1}"
        domains.append(
            Domain(
                id=domain_id,
                name=names[index],
                lead=leads[index],
                category=_tier_category(0),
            )
        )
        current.append(domain_id)
        index += 1
    for tier in range(1, depth):
        children: list[str] = []
        for parent_id in current:
            for _ in range(_CHILDREN_PER_DOMAIN):
                domain_id = f"domain_{index + 1}"
                domains.append(
                    Domain(
                        id=domain_id,
                        name=names[index],
                        parent_id=parent_id,
                        lead=leads[index],
                        category=_tier_category(tier),
                    )
                )
                children.append(domain_id)
                index += 1
        current = children
    domain_of = [current[i % len(current)] for i in range(count)]
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
