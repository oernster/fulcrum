"""Procedural generation of an org sized to a chosen people band.

The player picks a rough size; the generator builds a branching domain tree whose
depth and fan-out are chosen so the rolled-up headcount lands inside that band,
then fills every leaf with a cloned solvable cluster from a small pool. Tree
depth scales with size, so a small org is a shallow handful of domains and a
quarter-million-person org is a five-tier company; the tier names align to the
bottom of the vocabulary, so leaves are always Domains and only a deep enough
tree reaches Company at its root.

Headcount lives on the teams and rolls up the tree, so every unit's people are
exactly the sum of its teams. Solvability is guaranteed per leaf, not globally:
each cloned cluster reaches a great move on its own, which is the slice the
player scores when they drill into that domain.
"""

from __future__ import annotations

from random import Random

from fulcrum.application.cluster_pool import (
    assemble_clusters,
    build_cluster_pool,
    mean_cluster_people,
    pick_workload,
)
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import GROUP_CATEGORIES, Domain, Origin, OrgState, Team
from fulcrum.domain.org_size import DEFAULT_BAND, OrgSizeBand

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


# Each band's tree depth (its number of domain tiers). The leaf count is chosen
# per generation from the target people, so a band is always the same depth (its
# leaves are Domains, its root the tier the depth reaches) while its size ranges
# across the whole band. The tiny band has no entry: it is a single team.
_DEPTHS: dict[str, int] = {
    "small": 2,
    "medium": 3,
    "large": 4,
    "huge": 5,
    "massive": 5,
}


def _split(total: int, parts: int) -> list[int]:
    """Divide `total` into `parts` whole shares as evenly as possible."""
    base, extra = divmod(total, parts)
    return [base + 1 if index < extra else base for index in range(parts)]


def _build_tree(
    rng: Random, depth: int, leaf_count: int
) -> tuple[tuple[Domain, ...], tuple[str, ...]]:
    """Build a balanced tree of the given depth holding exactly leaf_count leaves.

    Each node's branching is chosen so the leaves spread evenly down the tiers;
    categories align to the bottom of the vocabulary, so leaves are Domains and the
    root is whichever tier the depth reaches. Returns the domains and the ordered
    leaf-domain ids the clusters attach to.
    """
    domains: list[Domain] = []
    leaf_ids: list[str] = []
    counter = [0]
    base = len(GROUP_CATEGORIES) - depth

    def add_node(parent_id: str | None, tier: int, leaves_here: int) -> None:
        counter[0] += 1
        domain_id = f"domain_{counter[0]}"
        domains.append(
            Domain(
                id=domain_id,
                name=rng.choice(_DOMAIN_NAMES),
                parent_id=parent_id,
                lead=rng.choice(_LEAD_NAMES),
                category=GROUP_CATEGORIES[base + tier],
            )
        )
        if tier == depth - 1:
            leaf_ids.append(domain_id)
            return
        tiers_below = depth - 1 - tier
        children = max(1, round(leaves_here ** (1 / tiers_below)))
        for share in _split(leaves_here, children):
            add_node(domain_id, tier + 1, share)

    add_node(None, 0, leaf_count)
    return tuple(domains), tuple(leaf_ids)


def _single_team_org(rng: Random, band: OrgSizeBand, workload: int) -> OrgState:
    """The tiny band: one self-contained team sized to the band, no hierarchy."""
    team = Team(
        id="team_1",
        name="Team 1",
        has_local_authority=True,
        headcount=rng.randint(band.min_people, band.max_people),
    )
    return OrgState(teams=(team,), workload=workload, origin=Origin.GENERATED)


def generate_level(rng: Random, band: OrgSizeBand = DEFAULT_BAND) -> OrgState:
    """Generate an org whose rolled-up headcount falls anywhere in the size band.

    The target people count is drawn uniformly across the band, then the tree is
    sized to it, so repeated generations spread over the whole range rather than
    clustering at the midpoint. A tiny org is a single team; every larger band
    fills each leaf with a cloned solvable cluster.
    """
    simulator = DeterministicSimulator()
    workload = pick_workload(rng)
    depth = _DEPTHS.get(band.key)
    if depth is None:
        return _single_team_org(rng, band, workload)
    target = rng.randint(band.min_people, band.max_people)
    leaf_count = max(1, round(target / mean_cluster_people()))
    domains, leaf_ids = _build_tree(rng, depth, leaf_count)
    pool = build_cluster_pool(rng, simulator, workload, leaf_count)
    teams, dependencies = assemble_clusters(rng, pool, leaf_ids)
    return OrgState(
        teams=teams,
        dependencies=dependencies,
        workload=workload,
        origin=Origin.GENERATED,
        domains=domains,
    )
