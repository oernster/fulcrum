"""Procedural level generation with a solvability guarantee.

A generated level is a densely coupled position with one authoritative team and
the rest lacking authority, so a collapsing or delegating move is always strong.
The randomness varies the flavour (size, delays, skew, workload), never the
existence of a solution, so every level is playable and provably has a great
move.

Larger levels are additionally grouped into domains, and the largest nest a
sub-domain, so they exercise the hierarchy, the navigable map and the
per-domain plan. The grouping is navigational metadata over the same teams, so
it never changes the score or the guaranteed great move.
"""

from __future__ import annotations

from random import Random

from fulcrum.application.game_session import enumerate_moves
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Dependency, Domain, Origin, OrgState, Team
from fulcrum.domain.simulation import MoveClassification

_TEAM_CHOICES: tuple[int, ...] = (3, 4, 5, 6, 7, 8)
_MIN_DELAY: int = 3
_MAX_DELAY: int = 6
_MIN_WORKLOAD: int = 6
_MAX_WORKLOAD: int = 9
_MIN_SKEW: float = 0.3
_MAX_SKEW: float = 0.9
_SKEW_DECIMALS: int = 2

# At or above the first threshold the teams are grouped into root domains; at or
# above the second one of those domains becomes a nested sub-domain, so the
# largest generated orgs are two levels deep. The grouping is metadata only.
_DOMAIN_THRESHOLD: int = 6
_SUBDOMAIN_THRESHOLD: int = 7
_ROOT_DOMAINS: int = 2

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


def _build_domains(
    rng: Random, count: int
) -> tuple[tuple[Domain, ...], list[str | None]]:
    """Return the domains and a per-team domain id for an org of `count` teams.

    Small orgs stay flat with no domains. From the domain threshold up, teams
    are grouped into root domains; from the sub-domain threshold up, one extra
    domain is nested under the first so the org is two levels deep.
    """
    if count < _DOMAIN_THRESHOLD:
        return (), [None] * count
    nested = count >= _SUBDOMAIN_THRESHOLD
    total = _ROOT_DOMAINS + (1 if nested else 0)
    names = rng.sample(_DOMAIN_NAMES, total)
    leads = rng.sample(_LEAD_NAMES, total)
    domains = [
        Domain(id=f"domain_{k + 1}", name=names[k], lead=leads[k])
        for k in range(_ROOT_DOMAINS)
    ]
    if nested:
        domains.append(
            Domain(
                id=f"domain_{_ROOT_DOMAINS + 1}",
                name=names[_ROOT_DOMAINS],
                parent_id="domain_1",
                lead=leads[_ROOT_DOMAINS],
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
