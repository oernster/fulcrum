"""Pure queries over the org's domain hierarchy and focused sub-org views.

The hierarchy is reconstructed from each domain's parent_id, so it nests to any
depth. A focused sub-org is the slice of the org inside one domain's subtree:
its teams and the dependencies internal to them, flattened so it can be scored
and played on its own, which is how the CTO drills into a domain to decide.
"""

from __future__ import annotations

from fulcrum.domain.models import Dependency, Domain, OrgState, Team


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


def focused_suborg(org: OrgState, domain_id: str) -> OrgState:
    """Flatten a domain's subtree into a standalone org for scoring and play.

    Teams keep their structural properties but drop their domain tag, and only
    dependencies internal to the subtree are kept, so the slice scores in
    isolation. Requires the subtree to contain at least one team.
    """
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
