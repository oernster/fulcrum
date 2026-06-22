"""Shared JSON serialization for org states and moves.

These helpers translate the domain's org and move objects to and from plain
dictionaries. They are the single conversion layer used when a plan is written
to or read from a JSON file, so the on-disk shape stays defined in one place.
"""

from __future__ import annotations

from fulcrum.domain.models import (
    DEFAULT_CATEGORY,
    DEFAULT_HEADCOUNT,
    Dependency,
    Domain,
    Origin,
    OrgState,
    Team,
)
from fulcrum.domain.moves import Move, MoveKind

_DEFAULT_SIZE = 1
_DEFAULT_OWNER = ""


def _team_to_dict(team: Team) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "has_local_authority": team.has_local_authority,
        "incentive_skew": team.incentive_skew,
        "domain_id": team.domain_id,
        "size": team.size,
        "owner": team.owner,
        "headcount": team.headcount,
    }


def _domain_to_dict(domain: Domain) -> dict:
    return {
        "id": domain.id,
        "name": domain.name,
        "parent_id": domain.parent_id,
        "lead": domain.lead,
        "category": domain.category,
        "headcount": domain.headcount,
    }


def _dependency_to_dict(dep: Dependency) -> dict:
    return {
        "upstream": dep.upstream,
        "downstream": dep.downstream,
        "propagation_delay": dep.propagation_delay,
    }


def org_to_dict(org: OrgState) -> dict:
    return {
        "teams": [_team_to_dict(t) for t in org.teams],
        "dependencies": [_dependency_to_dict(d) for d in org.dependencies],
        "workload": org.workload,
        "origin": org.origin.value,
        "domains": [_domain_to_dict(d) for d in org.domains],
    }


def move_to_dict(move: Move) -> dict:
    return {
        "kind": move.kind.value,
        "targets": list(move.targets),
        "label": move.label,
    }


def org_from_dict(data: dict) -> OrgState:
    teams = tuple(
        Team(
            t["id"],
            t["name"],
            t["has_local_authority"],
            t["incentive_skew"],
            t.get("domain_id"),
            t.get("size", _DEFAULT_SIZE),
            t.get("owner", _DEFAULT_OWNER),
            t.get("headcount", DEFAULT_HEADCOUNT),
        )
        for t in data["teams"]
    )
    dependencies = tuple(
        Dependency(d["upstream"], d["downstream"], d["propagation_delay"])
        for d in data["dependencies"]
    )
    domains = tuple(
        Domain(
            d["id"],
            d["name"],
            d.get("parent_id"),
            d.get("lead", ""),
            d.get("category", DEFAULT_CATEGORY),
            d.get("headcount", 0),
        )
        for d in data.get("domains", ())
    )
    return OrgState(
        teams=teams,
        dependencies=dependencies,
        workload=data["workload"],
        origin=Origin(data["origin"]),
        domains=domains,
    )


def move_from_dict(data: dict) -> Move:
    return Move(MoveKind(data["kind"]), tuple(data["targets"]), data["label"])
