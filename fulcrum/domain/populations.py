"""Bulk population accounting: every domain's headcount in one pass.

The scale pricing needs a resolution neighbourhood's population for every
escalating team. Asking hierarchy.headcount_in_domain per team rescans the
organisation each time, which priced a large org at minutes of planning;
this table walks the hierarchy once and answers every lookup from it.
"""

from __future__ import annotations

from fulcrum.domain.models import OrgState


def headcounts_by_domain(org: OrgState) -> dict[str, int]:
    """Every domain's subtree headcount, keyed by domain id.

    Matches hierarchy.headcount_in_domain for each id: a subtree's unit
    populations where any unit carries one, otherwise its team sizes.
    """
    children: dict[str | None, list[str]] = {}
    for domain in org.domains:
        children.setdefault(domain.parent_id, []).append(domain.id)
    own_units = {d.id: d.headcount for d in org.domains}
    own_teams: dict[str, int] = {d.id: 0 for d in org.domains}
    for team in org.teams:
        if team.domain_id in own_teams:
            own_teams[team.domain_id] += team.headcount
    # Children-first order: depth-first from the roots, reversed. Parent
    # ids are validated and cycles rejected, so this reaches every domain.
    ordered: list[str] = []
    frontier = list(children.get(None, ()))
    while frontier:
        current = frontier.pop()
        ordered.append(current)
        frontier.extend(children.get(current, ()))
    unit_totals: dict[str, int] = {}
    team_totals: dict[str, int] = {}
    for domain_id in reversed(ordered):
        unit_totals[domain_id] = own_units[domain_id] + sum(
            unit_totals[child] for child in children.get(domain_id, ())
        )
        team_totals[domain_id] = own_teams[domain_id] + sum(
            team_totals[child] for child in children.get(domain_id, ())
        )
    return {
        domain_id: unit_totals[domain_id] or team_totals[domain_id]
        for domain_id in ordered
    }
