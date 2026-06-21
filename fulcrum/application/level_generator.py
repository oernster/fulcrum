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

from dataclasses import dataclass
from random import Random

from fulcrum.application.cluster_pool import (
    assemble_clusters,
    build_cluster_pool,
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


@dataclass(frozen=True, slots=True)
class _Shape:
    """The tree a band is built as: how many tiers deep and how wide each tier."""

    depth: int
    fanout: int


# Each band's tree shape, chosen so leaves (a regular fanout**(depth-1)) times the
# roughly twenty-six people a cluster holds land near the band's midpoint. The
# tiny band has no entry: it is a single team, not a hierarchy.
_SHAPES: dict[str, _Shape] = {
    "small": _Shape(depth=2, fanout=3),
    "medium": _Shape(depth=3, fanout=6),
    "large": _Shape(depth=4, fanout=6),
    "huge": _Shape(depth=5, fanout=6),
    "massive": _Shape(depth=5, fanout=9),
}


def _build_hierarchy(
    rng: Random, shape: _Shape
) -> tuple[tuple[Domain, ...], tuple[str, ...]]:
    """Build a regular branching domain tree of the shape's depth and fan-out.

    A single root fans out `fanout` children per tier down to the leaf tier; the
    tier categories are aligned to the bottom of the vocabulary, so the leaves
    are Domains and the root is whichever tier the depth reaches. Returns the
    domains and the ordered leaf-domain ids the team clusters attach to.
    """
    domains: list[Domain] = []
    leaf_ids: list[str] = []
    counter = [0]
    base = len(GROUP_CATEGORIES) - shape.depth

    def add_node(parent_id: str | None, tier: int) -> None:
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
        if tier == shape.depth - 1:
            leaf_ids.append(domain_id)
            return
        for _ in range(shape.fanout):
            add_node(domain_id, tier + 1)

    add_node(None, 0)
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
    """Generate an org whose rolled-up headcount fills the chosen size band.

    A bandless tiny org is a single team; every larger band builds a tree sized
    to its people range and fills each leaf with a cloned solvable cluster, so a
    quarter-million-person org generates as quickly as a small one.
    """
    simulator = DeterministicSimulator()
    workload = pick_workload(rng)
    shape = _SHAPES.get(band.key)
    if shape is None:
        return _single_team_org(rng, band, workload)
    domains, leaf_ids = _build_hierarchy(rng, shape)
    pool = build_cluster_pool(rng, simulator, workload, len(leaf_ids))
    teams, dependencies = assemble_clusters(rng, pool, leaf_ids)
    return OrgState(
        teams=teams,
        dependencies=dependencies,
        workload=workload,
        origin=Origin.GENERATED,
        domains=domains,
    )
