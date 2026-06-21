"""Pure queries over the org's domain hierarchy and focused sub-org views.

The hierarchy is reconstructed from each domain's parent_id, so it nests to any
depth. A focused sub-org is the slice of the org inside one domain's subtree:
its teams and the dependencies internal to them, flattened so it can be scored
and played on its own, which is how the CTO drills into a domain to decide.
"""

from __future__ import annotations

from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind

_SKEW_DECIMALS = 2

# The move kinds that translate cleanly from an aggregate (non-leaf) scope down
# to the real teams beneath it: empowering, realigning and stabilising a child
# domain all map to the same act over its teams. Boundary-collapse at a level
# means merging whole sub-orgs and is handled only at the team level for now.
AGGREGATE_MOVE_KINDS = (
    MoveKind.DELEGATE_AUTHORITY,
    MoveKind.REALIGN_INCENTIVES,
    MoveKind.STABILISE_INTERFACES,
)


def root_domains(org: OrgState) -> tuple[Domain, ...]:
    """Top-level domains: those with no parent."""
    return tuple(d for d in org.domains if d.parent_id is None)


def child_domains(org: OrgState, parent_id: str) -> tuple[Domain, ...]:
    """Domains whose immediate parent is the given domain."""
    return tuple(d for d in org.domains if d.parent_id == parent_id)


def domain_subtree_ids(org: OrgState, domain_id: str) -> frozenset[str]:
    """The domain and every domain nested beneath it, by id."""
    children: dict[str | None, list[str]] = {}
    for domain in org.domains:
        children.setdefault(domain.parent_id, []).append(domain.id)
    collected: list[str] = []
    frontier = [domain_id]
    while frontier:
        current = frontier.pop()
        collected.append(current)
        frontier.extend(children.get(current, ()))
    return frozenset(collected)


def teams_in_domain(
    org: OrgState, domain_id: str, recursive: bool = True
) -> tuple[Team, ...]:
    """Teams assigned to a domain, by default including its sub-domains."""
    if recursive:
        ids = domain_subtree_ids(org, domain_id)
        return tuple(t for t in org.teams if t.domain_id in ids)
    return tuple(t for t in org.teams if t.domain_id == domain_id)


def domain_has_teams(org: OrgState, domain_id: str) -> bool:
    """Whether a domain's subtree contains at least one team to focus on."""
    ids = domain_subtree_ids(org, domain_id)
    return any(t.domain_id in ids for t in org.teams)


def _has_majority_authority(teams: tuple[Team, ...]) -> bool:
    """Whether at least half of a grouping's teams decide locally."""
    held = sum(1 for t in teams if t.has_local_authority)
    return held * 2 >= len(teams)


def _aggregate_deps(
    org: OrgState, node_of_team: dict[str, str]
) -> tuple[Dependency, ...]:
    """Roll real dependencies up to mean-delay edges between the child nodes."""
    totals: dict[tuple[str, str], int] = {}
    counts: dict[tuple[str, str], int] = {}
    for dep in org.dependencies:
        source = node_of_team.get(dep.upstream)
        target = node_of_team.get(dep.downstream)
        if source is not None and target is not None and source != target:
            key = (source, target)
            totals[key] = totals.get(key, 0) + dep.propagation_delay
            counts[key] = counts.get(key, 0) + 1
    return tuple(
        Dependency(s, t, round(totals[(s, t)] / counts[(s, t)])) for (s, t) in totals
    )


def _aggregate_section(org: OrgState, parent_id: str) -> OrgState:
    """Score a non-leaf domain as its immediate children, each a rolled-up node.

    Each child domain becomes one synthetic team carrying its subtree's majority
    authority and mean incentive skew, with dependencies aggregated between the
    children, so a structural move at this level (empower a department, realign a
    division) carries the proportional weight a team move has inside a leaf.
    """
    nodes: list[Team] = []
    node_of_team: dict[str, str] = {}
    for child in child_domains(org, parent_id):
        teams = teams_in_domain(org, child.id)
        if not teams:
            continue
        for team in teams:
            node_of_team[team.id] = child.id
        skew = round(sum(t.incentive_skew for t in teams) / len(teams), _SKEW_DECIMALS)
        nodes.append(Team(child.id, child.name, _has_majority_authority(teams), skew))
    return OrgState(
        teams=tuple(nodes),
        dependencies=_aggregate_deps(org, node_of_team),
        workload=org.workload,
        origin=org.origin,
    )


def focused_suborg(org: OrgState, domain_id: str) -> OrgState:
    """The standalone org scored when a domain is focused.

    A non-leaf domain is scored as its immediate children rolled up into one
    decision-node each, so structural moves appear at every level. A leaf domain
    is its own teams, flattened with only their internal dependencies. Either way
    the slice scores and plays in isolation.
    """
    if child_domains(org, domain_id):
        return _aggregate_section(org, domain_id)
    ids = domain_subtree_ids(org, domain_id)
    teams = tuple(
        Team(t.id, t.name, t.has_local_authority, t.incentive_skew)
        for t in org.teams
        if t.domain_id in ids
    )
    inside = {t.id for t in teams}
    deps = tuple(
        d for d in org.dependencies if d.upstream in inside and d.downstream in inside
    )
    return OrgState(
        teams=teams, dependencies=deps, workload=org.workload, origin=org.origin
    )


def translate_focused_move(org: OrgState, focus_id: str | None, move: Move) -> Move:
    """Map a move played at an aggregate scope onto the real teams beneath it.

    At a non-leaf scope the move's targets are child-domain ids; empowering or
    realigning a child means doing so to every team in its subtree. A whole-org or
    leaf scope already targets real teams, so the move is returned unchanged.
    """
    if focus_id is None or not child_domains(org, focus_id):
        return move
    if not move.targets:
        return move
    team_ids = tuple(
        team.id for child_id in move.targets for team in teams_in_domain(org, child_id)
    )
    return Move(move.kind, team_ids, move.label)


def boundary_dependencies(org: OrgState, domain_id: str) -> tuple[Dependency, ...]:
    """Cross-boundary dependencies: exactly one endpoint inside the subtree.

    These are the inter-domain surfaces the CTO owns, as opposed to the
    domain-local dependencies a domain lead can resolve internally.
    """
    ids = domain_subtree_ids(org, domain_id)
    inside = {t.id for t in org.teams if t.domain_id in ids}
    return tuple(
        d
        for d in org.dependencies
        if (d.upstream in inside) != (d.downstream in inside)
    )


def headcount_in_domain(org: OrgState, domain_id: str) -> int:
    """People in a domain's subtree: its units' populations, or its team sizes."""
    ids = domain_subtree_ids(org, domain_id)
    unit_total = sum(domain.headcount for domain in org.domains if domain.id in ids)
    return unit_total or sum(team.headcount for team in teams_in_domain(org, domain_id))


def total_headcount(org: OrgState) -> int:
    """Total people: the units' populations, or team sizes if units carry none."""
    unit_total = sum(domain.headcount for domain in org.domains)
    return unit_total or sum(team.headcount for team in org.teams)
