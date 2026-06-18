"""Procedural generation of deep, clustered, section-solvable organisations.

A generated org models a large enterprise: a handful of leaf clusters of teams,
nested four or five tiers deep (division, department and so on down to the leaf),
with people counts that roll up into the hundreds of thousands. Each leaf cluster
is a densely coupled puzzle with one authoritative team and the rest lacking
authority, so a collapsing or delegating move is strong inside it. Clusters are
linked only sparsely across the org, so the whole position stays legible.

Solvability is guaranteed per section, not globally. Every leaf cluster is
resampled until its own focused sub-org reaches a great move, which is exactly
the slice the player scores when they drill into that domain. The cross-cluster
links never enter a focused slice, so the guarantee holds however the org is
assembled, and there is no global resample to stall on a large dense position.
This is the structural meaning of "a great move may live within a small domain":
the whole org need not present one, but every section the player drills into
does.
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

_LOOKAHEAD: int = 10
_MIN_DELAY: int = 3
_MAX_DELAY: int = 6
_MIN_WORKLOAD: int = 6
_MAX_WORKLOAD: int = 9
_MIN_SKEW: float = 0.3
_MAX_SKEW: float = 0.9
_SKEW_DECIMALS: int = 2

# Hierarchy shape. The org nests four or five tiers deep under two root
# divisions, branching by at most two at each tier, with a handful of leaf
# clusters spread across the bottom. Teams live only in the leaf clusters, so a
# generated org reads like a real multi-level structure rather than one flat
# level and exercises the hierarchy, the navigable map and per-domain play.
_ROOT_DIVISIONS: int = 2
_FANOUT: int = 2
_DEPTH_CHOICES: tuple[int, ...] = (4, 5)
_LEAF_CHOICES: tuple[int, ...] = (5, 6, 7)
_TEAMS_PER_LEAF_CHOICES: tuple[int, ...] = (4, 5)

# A leaf cluster in a huge org stands for a sizeable unit, so people counts are
# large: the per-team count rolls up through the domains into an org total in the
# hundreds of thousands without a rendered node per person. Headcount is
# descriptive and never changes the structural score.
_MIN_PEOPLE: int = 400
_MAX_PEOPLE: int = 9000

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


def _split(total: int, parts: int) -> tuple[int, ...]:
    """Split a count into `parts` near-equal pieces, each at least one."""
    base, extra = divmod(total, parts)
    return tuple(base + 1 if i < extra else base for i in range(parts))


def _build_hierarchy(
    rng: Random, depth: int, leaf_count: int
) -> tuple[tuple[Domain, ...], tuple[str, ...]]:
    """Build a domain tree `depth` tiers deep with `leaf_count` leaf clusters.

    The leaves are distributed across two root divisions and branch by at most
    two at each tier, so every leaf sits at the bottom tier and the tree reaches
    the requested depth. Returns the domains and the ordered leaf-domain ids the
    team clusters attach to.
    """
    domains: list[Domain] = []
    leaf_ids: list[str] = []
    counter = [0]

    def add_node(parent_id: str | None, tier: int, leaves_here: int) -> None:
        counter[0] += 1
        domain_id = f"domain_{counter[0]}"
        domains.append(
            Domain(
                id=domain_id,
                name=rng.choice(_DOMAIN_NAMES),
                parent_id=parent_id,
                lead=rng.choice(_LEAD_NAMES),
                category=_tier_category(tier),
            )
        )
        if tier == depth - 1:
            leaf_ids.append(domain_id)
            return
        children = min(_FANOUT, leaves_here)
        for share in _split(leaves_here, children):
            add_node(domain_id, tier + 1, share)

    for share in _split(leaf_count, _ROOT_DIVISIONS):
        add_node(None, 0, share)
    return tuple(domains), tuple(leaf_ids)


def _random_cluster(
    rng: Random,
    simulator: DeterministicSimulator,
    workload: int,
    start_index: int,
    size: int,
) -> tuple[tuple[Team, ...], tuple[Dependency, ...]]:
    """Generate one leaf cluster whose own focused sub-org reaches a great move.

    A cluster is one authoritative team and the rest without authority, densely
    coupled. Only its flavour (skew, delays, headcount) is resampled, never its
    solvability, so it always offers a reachable great move when drilled into.
    """
    while True:
        teams = tuple(
            Team(
                id=f"team_{start_index + i + 1}",
                name=f"Team {start_index + i + 1}",
                has_local_authority=(i == 0),
                incentive_skew=round(rng.uniform(_MIN_SKEW, _MAX_SKEW), _SKEW_DECIMALS),
                headcount=rng.randint(_MIN_PEOPLE, _MAX_PEOPLE),
            )
            for i in range(size)
        )
        ids = [team.id for team in teams]
        dependencies = tuple(
            Dependency(ids[i], ids[j], rng.randint(_MIN_DELAY, _MAX_DELAY))
            for i in range(size)
            for j in range(i + 1, size)
        )
        section = OrgState(
            teams=teams,
            dependencies=dependencies,
            workload=workload,
            origin=Origin.GENERATED,
        )
        if _reaches_great_move(section, simulator):
            return teams, dependencies


def _cross_dependencies(
    rng: Random, clusters: list[tuple[str, ...]]
) -> tuple[Dependency, ...]:
    """Link consecutive clusters by a single dependency each: a sparse surface.

    These are the only inter-cluster edges, so the cross-domain dependency count
    grows with the number of clusters rather than the square of the team count,
    and they never fall inside a focused leaf slice.
    """
    edges: list[Dependency] = []
    for index in range(len(clusters) - 1):
        upstream = rng.choice(clusters[index])
        downstream = rng.choice(clusters[index + 1])
        edges.append(
            Dependency(upstream, downstream, rng.randint(_MIN_DELAY, _MAX_DELAY))
        )
    return tuple(edges)


def _build_clusters(
    rng: Random,
    simulator: DeterministicSimulator,
    workload: int,
    leaf_ids: tuple[str, ...],
) -> tuple[tuple[Team, ...], tuple[Dependency, ...]]:
    """Fill every leaf domain with a solvable cluster and link them sparsely."""
    teams: list[Team] = []
    dependencies: list[Dependency] = []
    clusters: list[tuple[str, ...]] = []
    for leaf_id in leaf_ids:
        size = rng.choice(_TEAMS_PER_LEAF_CHOICES)
        cluster_teams, cluster_deps = _random_cluster(
            rng, simulator, workload, len(teams), size
        )
        tagged = tuple(
            Team(
                id=team.id,
                name=team.name,
                has_local_authority=team.has_local_authority,
                incentive_skew=team.incentive_skew,
                domain_id=leaf_id,
                headcount=team.headcount,
            )
            for team in cluster_teams
        )
        teams.extend(tagged)
        dependencies.extend(cluster_deps)
        clusters.append(tuple(team.id for team in tagged))
    dependencies.extend(_cross_dependencies(rng, clusters))
    return tuple(teams), tuple(dependencies)


def generate_level(rng: Random) -> OrgState:
    """Generate a deep, clustered org whose every leaf section is solvable.

    The whole position need not present a great move; each leaf cluster does,
    and that is the slice the player scores when they drill into a domain. So a
    large dense org is generated quickly, with no global resample to stall on.
    """
    simulator = DeterministicSimulator()
    depth = rng.choice(_DEPTH_CHOICES)
    leaf_count = rng.choice(_LEAF_CHOICES)
    workload = rng.randint(_MIN_WORKLOAD, _MAX_WORKLOAD)
    domains, leaf_ids = _build_hierarchy(rng, depth, leaf_count)
    teams, dependencies = _build_clusters(rng, simulator, workload, leaf_ids)
    return OrgState(
        teams=teams,
        dependencies=dependencies,
        workload=workload,
        origin=Origin.GENERATED,
        domains=domains,
    )


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
