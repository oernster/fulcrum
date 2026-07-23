"""Build the node-and-edge view model for one drill level of the org map.

At the top level the nodes are the root domains (each aggregating its whole
subtree) plus any unassigned teams; drilling into a domain shows its child
domains and the teams directly in it. Dependencies are aggregated to edges
between the nodes at the current level, so the map stays legible at any scale.
"""

from __future__ import annotations

from fulcrum.application.dto import MapEdge, MapNode
from fulcrum.domain.hierarchy import (
    child_domains,
    domain_subtree_ids,
    headcount_in_domain,
    root_domains,
    teams_in_domain,
)
from fulcrum.domain.models import OrgState

_KIND_DOMAIN = "domain"
_KIND_TEAM = "team"
_FULL = 1.0
_NONE = 0.0


def build_level(
    org: OrgState, parent_id: str | None = None
) -> tuple[tuple[MapNode, ...], tuple[MapEdge, ...]]:
    """Return the nodes and aggregated edges to draw at one drill level."""
    if parent_id is None:
        domains = root_domains(org)
        direct_teams = tuple(t for t in org.teams if t.domain_id is None)
    else:
        domains = child_domains(org, parent_id)
        direct_teams = teams_in_domain(org, parent_id, recursive=False)

    node_of: dict[str, str] = {}
    nodes: list[MapNode] = []
    for domain in domains:
        ids = domain_subtree_ids(org, domain.id)
        members = [t for t in org.teams if t.domain_id in ids]
        for team in members:
            node_of[team.id] = domain.id
        for sub_id in ids:
            node_of[sub_id] = domain.id
        nodes.append(
            MapNode(
                kind=_KIND_DOMAIN,
                id=domain.id,
                label=domain.name,
                team_count=len(members),
                authority_ratio=_authority_ratio(members),
                owner=domain.lead,
                category=domain.category,
                headcount=headcount_in_domain(org, domain.id),
            )
        )
    for team in direct_teams:
        node_of[team.id] = team.id
        nodes.append(
            MapNode(
                kind=_KIND_TEAM,
                id=team.id,
                label=team.name,
                team_count=1,
                authority_ratio=_FULL if team.has_local_authority else _NONE,
                owner=team.owner,
                headcount=team.headcount,
            )
        )
    return tuple(nodes), _edges(org, node_of)


def _edges(org: OrgState, node_of: dict[str, str]) -> tuple[MapEdge, ...]:
    """Aggregate edges between the level's nodes; endpoints may be teams or
    domains, each represented by the node holding it at this level."""
    weights: dict[tuple[str, str], int] = {}
    for dep in org.dependencies:
        source = node_of.get(dep.upstream)
        target = node_of.get(dep.downstream)
        if source is not None and target is not None and source != target:
            key = (source, target)
            weights[key] = weights.get(key, 0) + 1
    return tuple(MapEdge(source, target, w) for (source, target), w in weights.items())


def _authority_ratio(members: list) -> float:
    if not members:
        return _NONE
    held = sum(1 for team in members if team.has_local_authority)
    return held / len(members)
