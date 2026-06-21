"""A pool of solvable team clusters, cloned to fill every leaf of an org.

Generation must stay fast even for a quarter of a million people, so the cost
of finding section-solvable clusters is paid a fixed number of times, not once
per leaf. A small pool of clusters is resampled until each, scored on its own,
reaches a great move; those templates are then cloned across the org's leaves
with fresh ids, names and headcounts. A clone keeps its template's authority
pattern, incentive skews and dependency delays, and headcount never changes the
structural score, so every clone stays exactly as solvable as the template it
came from. Per-section solvability therefore holds for thousands of leaves while
the simulator runs only a couple of dozen times.
"""

from __future__ import annotations

from random import Random

from fulcrum.application.game_session import enumerate_moves
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Dependency, Origin, OrgState, Team
from fulcrum.domain.moves import apply_move
from fulcrum.domain.simulation import MoveClassification

_LOOKAHEAD: int = 10
_MIN_DELAY: int = 3
_MAX_DELAY: int = 6
_MIN_WORKLOAD: int = 6
_MAX_WORKLOAD: int = 9
_MIN_SKEW: float = 0.3
_MAX_SKEW: float = 0.9
_SKEW_DECIMALS: int = 2

# A team is four to six people, occasionally eight to twelve, never more. Every
# person sits in a team; team headcounts roll up the tree, so a unit's people are
# exactly the sum of its teams. Headcount never changes the structural score.
_TEAM_MIN: int = 4
_TEAM_MAX: int = 6
_BIG_TEAM_MIN: int = 8
_BIG_TEAM_MAX: int = 12
_BIG_TEAM_CHANCE: float = 0.15

# Each leaf holds a small cluster of four or five teams: large enough to pose a
# coupling puzzle with a reachable great move, small enough to read at a glance.
_TEAMS_PER_LEAF_CHOICES: tuple[int, ...] = (4, 5)

# The most distinct cluster templates ever built. A small org builds one template
# per leaf; a large one reuses this many across all its leaves, so the simulator
# runs a bounded number of times however big the org grows.
_POOL_SIZE_CAP: int = 24

# A cluster is resampled until it is section-solvable, but never more than this:
# clusters are reliably solvable, so the cap is only a guard against an unlucky
# run looping forever. If it is ever reached, the last sample is used as-is, since
# a section with a weaker move beats a generation that never returns.
_MAX_CLUSTER_TRIES: int = 200


def pick_workload(rng: Random) -> int:
    """Choose the org-wide decision workload the clusters are scored against."""
    return rng.randint(_MIN_WORKLOAD, _MAX_WORKLOAD)


def _team_headcount(rng: Random) -> int:
    """A team is four to six people, occasionally eight to twelve."""
    if rng.random() < _BIG_TEAM_CHANCE:
        return rng.randint(_BIG_TEAM_MIN, _BIG_TEAM_MAX)
    return rng.randint(_TEAM_MIN, _TEAM_MAX)


def mean_cluster_people() -> float:
    """Average people in a leaf cluster, for sizing an org to a target count."""
    small = (_TEAM_MIN + _TEAM_MAX) / 2
    big = (_BIG_TEAM_MIN + _BIG_TEAM_MAX) / 2
    mean_team = (1 - _BIG_TEAM_CHANCE) * small + _BIG_TEAM_CHANCE * big
    mean_teams = sum(_TEAMS_PER_LEAF_CHOICES) / len(_TEAMS_PER_LEAF_CHOICES)
    return mean_teams * mean_team


def has_great_move(
    org: OrgState, simulator: DeterministicSimulator | None = None
) -> bool:
    """Return whether at least one candidate move is classified great."""
    sim = simulator or DeterministicSimulator()
    return any(
        valuation.classification == MoveClassification.GREAT
        for valuation in sim.valuate_moves(org, enumerate_moves(org))
    )


def reaches_great_move(
    org: OrgState, simulator: DeterministicSimulator, lookahead: int = _LOOKAHEAD
) -> bool:
    """Whether a great move is reachable within `lookahead` greedy improvements.

    A great move need not be available now: following the best improving move
    step by step, the position may open one up within a few moves, which is
    enough for a playable section.
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


def _sample_cluster(
    rng: Random, start_index: int, size: int
) -> tuple[tuple[Team, ...], tuple[Dependency, ...]]:
    """Sample one densely coupled cluster, without checking its solvability.

    One authoritative team and the rest without authority, every pair linked, so
    a collapsing or delegating move is strong inside it.
    """
    teams = tuple(
        Team(
            id=f"team_{start_index + i + 1}",
            name=f"Team {start_index + i + 1}",
            has_local_authority=(i == 0),
            incentive_skew=round(rng.uniform(_MIN_SKEW, _MAX_SKEW), _SKEW_DECIMALS),
            headcount=_team_headcount(rng),
        )
        for i in range(size)
    )
    ids = [team.id for team in teams]
    dependencies = tuple(
        Dependency(ids[i], ids[j], rng.randint(_MIN_DELAY, _MAX_DELAY))
        for i in range(size)
        for j in range(i + 1, size)
    )
    return teams, dependencies


def _random_cluster(
    rng: Random,
    simulator: DeterministicSimulator,
    workload: int,
    start_index: int,
    size: int,
) -> tuple[tuple[Team, ...], tuple[Dependency, ...]]:
    """Resample a cluster until its own sub-org reaches a great move.

    Only its flavour (skew, delays, headcount) is resampled, never the guarantee,
    so the returned cluster offers a reachable great move when drilled into. The
    resampling is capped: if no sample is solvable within the cap the last one is
    returned, so an unlucky run can never loop forever.
    """
    teams, dependencies = _sample_cluster(rng, start_index, size)
    for _ in range(_MAX_CLUSTER_TRIES):
        section = OrgState(
            teams=teams,
            dependencies=dependencies,
            workload=workload,
            origin=Origin.GENERATED,
        )
        if reaches_great_move(section, simulator):
            return teams, dependencies
        teams, dependencies = _sample_cluster(rng, start_index, size)
    return teams, dependencies


def build_cluster_pool(
    rng: Random,
    simulator: DeterministicSimulator,
    workload: int,
    leaf_count: int,
) -> tuple[tuple[tuple[Team, ...], tuple[Dependency, ...]], ...]:
    """Build the distinct solvable templates the leaves are cloned from.

    A small org gets one template per leaf; a large one is capped, so the
    simulator runs a bounded number of times however many leaves there are.
    """
    count = min(_POOL_SIZE_CAP, max(1, leaf_count))
    templates = [
        _random_cluster(
            rng, simulator, workload, 0, rng.choice(_TEAMS_PER_LEAF_CHOICES)
        )
        for _ in range(count)
    ]
    return tuple(templates)


def clone_cluster(
    template: tuple[tuple[Team, ...], tuple[Dependency, ...]],
    rng: Random,
    domain_id: str,
    start_index: int,
) -> tuple[tuple[Team, ...], tuple[Dependency, ...]]:
    """Copy a template into a leaf with fresh ids, names and headcounts.

    Authority, skew and dependency delays carry over unchanged, so the clone is
    exactly as solvable as the template; only the cosmetic identity and the
    people count, which does not affect the score, are renewed.
    """
    template_teams, template_deps = template
    id_map: dict[str, str] = {}
    teams: list[Team] = []
    for offset, team in enumerate(template_teams):
        new_id = f"team_{start_index + offset + 1}"
        id_map[team.id] = new_id
        teams.append(
            Team(
                id=new_id,
                name=f"Team {start_index + offset + 1}",
                has_local_authority=team.has_local_authority,
                incentive_skew=team.incentive_skew,
                domain_id=domain_id,
                headcount=_team_headcount(rng),
            )
        )
    deps = tuple(
        Dependency(id_map[dep.upstream], id_map[dep.downstream], dep.propagation_delay)
        for dep in template_deps
    )
    return tuple(teams), deps


def _cross_dependencies(
    rng: Random, clusters: list[tuple[str, ...]]
) -> tuple[Dependency, ...]:
    """Link consecutive clusters by a single dependency each: a sparse surface.

    These are the only inter-cluster edges, so the cross-domain dependency count
    grows with the number of clusters rather than the square of the team count,
    and they never fall inside a focused leaf slice.
    """
    edges = [
        Dependency(
            rng.choice(clusters[index]),
            rng.choice(clusters[index + 1]),
            rng.randint(_MIN_DELAY, _MAX_DELAY),
        )
        for index in range(len(clusters) - 1)
    ]
    return tuple(edges)


def assemble_clusters(
    rng: Random,
    pool: tuple[tuple[tuple[Team, ...], tuple[Dependency, ...]], ...],
    leaf_ids: tuple[str, ...],
) -> tuple[tuple[Team, ...], tuple[Dependency, ...]]:
    """Fill every leaf with a cloned template and link the clusters sparsely."""
    teams: list[Team] = []
    dependencies: list[Dependency] = []
    clusters: list[tuple[str, ...]] = []
    for index, leaf_id in enumerate(leaf_ids):
        cloned_teams, cloned_deps = clone_cluster(
            pool[index % len(pool)], rng, leaf_id, len(teams)
        )
        teams.extend(cloned_teams)
        dependencies.extend(cloned_deps)
        clusters.append(tuple(team.id for team in cloned_teams))
    dependencies.extend(_cross_dependencies(rng, clusters))
    return tuple(teams), tuple(dependencies)
