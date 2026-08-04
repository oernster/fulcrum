#!/usr/bin/env python3
"""Regenerate the matrixed-enterprise calibration case.

The case models a ~6,000-person organisation as a real drillable hierarchy:
the company roof holds a leadership unit plus seven delivery units, each unit
holds sub-units, an oversized sub-unit splits into led groups and every leaf
holds a handful of teams of three to eight people, so no lead anywhere
coordinates more than a sane span. Line lead teams (unit, sub-unit and group)
hold local authority on paper but the matrix overlay (a programme office and
an engineering chapter, both unmodelled claimants) claims every one of them,
so no decision class in the delivery organisation resolves cleanly and queues
cascade toward the one clean executive team. Cross-unit dependencies carry the
original case's delayed chain at team level.

The generator is deterministic: the same seed writes byte-identical JSON, so
the committed case is reproducible from this script alone, which the suite
asserts. Run it from the repository root after any change, then re-score:

    python generate_matrixed_enterprise.py
    python calibrate.py
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from fulcrum.domain.hierarchy import total_headcount
from fulcrum.domain.simulation import DEFAULT_PARAMETERS, evaluate
from fulcrum.infrastructure.json_serialization import org_from_dict

ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = ROOT / "examples" / "calibration" / "matrixed-enterprise.json"

_SEED = 20260731
_WORKLOAD = 6
# The case's headline size; main() refuses to write a file that misses it.
TARGET_PEOPLE = 6_000

_MIN_TEAM = 3
_MAX_TEAM = 8
_LEAD_MIN = 5
_LEAD_MAX = 8
_EXEC_HEADCOUNT = 6
_EXEC_SKEW = 0.1

_SKEW_JITTER = 0.12
_SKEW_FLOOR = 0.05
_SKEW_CEILING = 0.9
_LEAD_SKEW_DROP = 0.15
_LEAD_SKEW_FLOOR = 0.1
_SKEW_DECIMALS = 2

_EXEC_TO_UNIT_DELAY = 3
_LEAD_TO_SUB_DELAY = 2
_SUB_TO_TEAM_DELAY = 2
_SUB_TO_GROUP_DELAY = 1

# A sub-unit bigger than this splits into led groups (see _add_groups).
_MAX_LEAF_PEOPLE = 45

_PMO = "pmo"
_CHAPTER_ENG = "chapter_eng"

# One entry per unit: id, name, population, baseline incentive skew and the
# matrix claimant on its line leadership (None keeps the leadership clean).
# Populations and skews carry the original flat case's numbers onto real teams.
_UNITS = (
    ("leadership", "Group leadership", 200, 0.3, None),
    ("core", "Core product", 1200, 0.4, _PMO),
    ("platform", "Platform", 900, 0.5, _CHAPTER_ENG),
    ("payments", "Payments", 800, 0.4, _PMO),
    ("data", "Data", 700, 0.6, _CHAPTER_ENG),
    ("infra", "Infrastructure", 800, 0.5, _CHAPTER_ENG),
    ("intl", "International", 900, 0.5, _PMO),
    ("qa", "Quality", 500, 0.7, _PMO),
)

# The sub-units each unit divides into; its population is shared across them.
_UNIT_THEMES = {
    "leadership": ("Programme office", "Engineering chapters"),
    "core": (
        "Checkout",
        "Catalogue",
        "Search",
        "Mobile",
        "Web",
        "Growth",
        "Onboarding",
    ),
    "platform": ("API", "Runtime", "Developer experience", "Messaging", "Storage"),
    "payments": ("Cards", "Ledger", "Payouts", "Risk", "Reconciliation"),
    "data": ("Analytics", "Pipelines", "Reporting", "ML platform"),
    "infra": (
        "Compute",
        "Networking",
        "Databases",
        "Observability",
        "Security ops",
    ),
    "intl": ("EMEA", "APAC", "LATAM", "Localisation", "Compliance"),
    "qa": ("Test engineering", "Release", "Automation"),
}

# The original case's delayed dependency chain, realised as sampled team-level
# edges: upstream unit, downstream unit, propagation delay, team pairs.
_CROSS_UNIT_EDGES = (
    ("platform", "core", 4, 5),
    ("platform", "payments", 4, 4),
    ("infra", "platform", 3, 4),
    ("data", "core", 3, 4),
    ("core", "intl", 5, 4),
    ("qa", "core", 2, 4),
    ("qa", "payments", 2, 3),
)

_CALIBRATION = {
    "label": "Matrixed enterprise (~6,000)",
    "expected_min": 0,
    "expected_max": 30,
    "note": (
        "matrix overlay on a delayed dependency chain; the documented-collapse shape"
    ),
}


def _team_sizes(rng: random.Random, population: int) -> list[int]:
    """Split a population into varied team sizes of three to eight people."""
    if population < _MIN_TEAM:
        raise ValueError(f"population {population} cannot form a team")
    sizes: list[int] = []
    remaining = population
    while remaining > _MAX_TEAM + _MIN_TEAM:
        size = rng.randint(_MIN_TEAM, _MAX_TEAM)
        sizes.append(size)
        remaining -= size
    if remaining <= _MAX_TEAM:
        sizes.append(remaining)
    else:
        half = remaining // 2
        sizes.extend((half, remaining - half))
    return sizes


def _skew(rng: random.Random, base: float) -> float:
    value = base + rng.uniform(-_SKEW_JITTER, _SKEW_JITTER)
    return round(min(_SKEW_CEILING, max(_SKEW_FLOOR, value)), _SKEW_DECIMALS)


def _lead_skew(base: float) -> float:
    return round(max(_LEAD_SKEW_FLOOR, base - _LEAD_SKEW_DROP), _SKEW_DECIMALS)


def _team(
    team_id: str,
    name: str,
    authority: bool,
    skew: float,
    domain_id: str,
    headcount: int,
) -> dict:
    return {
        "id": team_id,
        "name": name,
        "has_local_authority": authority,
        "incentive_skew": skew,
        "domain_id": domain_id,
        "size": 1,
        "owner": "",
        "headcount": headcount,
    }


def _domain(domain_id: str, name: str, parent_id: str | None, category: str) -> dict:
    return {
        "id": domain_id,
        "name": name,
        "parent_id": parent_id,
        "lead": "",
        "category": category,
        "headcount": 0,
    }


def _dependency(upstream: str, downstream: str, delay: int) -> dict:
    return {"upstream": upstream, "downstream": downstream, "propagation_delay": delay}


@dataclass(slots=True)
class _Case:
    """The lists a case is built from, plus the per-unit delivery index.

    One accumulator passed down keeps every builder flat and the random
    draws in their published order, which is what makes the JSON reproduce.
    """

    rng: random.Random
    teams: list[dict] = field(default_factory=list)
    domains: list[dict] = field(default_factory=list)
    dependencies: list[dict] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    delivery: dict[str, list[str]] = field(default_factory=dict)


def _add_groups(case: _Case, unit, theme: str, sub: tuple, people: int) -> list:
    """Split an oversized sub-unit into led groups; return the leaf parents.

    One lead coordinating thirty-odd teams in a flat leaf is not a hierarchy,
    it is a queue wearing one's clothes, and the case models a drillable
    organisation. So a sub-unit over the leaf cap divides into groups, each
    with its own lead and a handful of teams.
    """
    _unit_id, _name, _population, base_skew, claimant = unit
    sub_id, sub_lead_id = sub
    count = -(-people // _MAX_LEAF_PEOPLE)
    if count == 1:
        return [(sub_id, sub_lead_id, people)]
    parents: list = []
    share, extra = divmod(people, count)
    for group in range(1, count + 1):
        group_people = share + (1 if group <= extra else 0)
        group_id = f"{sub_id}_g{group}"
        label = f"{theme} group {group}"
        case.domains.append(_domain(group_id, label, sub_id, "Department"))
        lead_id = f"{group_id}_lead"
        heads = case.rng.randint(_LEAD_MIN, _LEAD_MAX)
        skew = _lead_skew(base_skew)
        case.teams.append(_team(lead_id, f"{label} lead", True, skew, group_id, heads))
        case.dependencies.append(_dependency(sub_lead_id, lead_id, _SUB_TO_GROUP_DELAY))
        if claimant is not None:
            # The matrix claims line leadership all the way down: a group
            # lead is as dual-reported as the sub-unit lead above it.
            case.claims.append({"claimant": claimant, "subject": lead_id})
        parents.append((group_id, lead_id, group_people - heads))
    return parents


def _add_leaf_teams(case: _Case, unit, theme: str, sub_id: str, parents: list) -> None:
    """Emit the delivery teams under each leaf parent, wired to its lead."""
    unit_id, _name, _population, base_skew, _claimant = unit
    number = 0
    for parent_id, parent_lead_id, people in parents:
        for heads in _team_sizes(case.rng, people):
            number += 1
            team_id = f"{sub_id}_t{number}"
            name = f"{theme} team {number}"
            skew = _skew(case.rng, base_skew)
            case.teams.append(_team(team_id, name, False, skew, parent_id, heads))
            case.dependencies.append(
                _dependency(parent_lead_id, team_id, _SUB_TO_TEAM_DELAY)
            )
            case.delivery[unit_id].append(team_id)


def _add_sub_unit(
    case: _Case, unit, theme: str, unit_lead_id: str, people: int
) -> None:
    """Add one sub-unit: its domain, its claimed lead and everything under it."""
    unit_id, _name, _population, base_skew, claimant = unit
    sub_id = f"{unit_id}_{theme.lower().replace(' ', '_')}"
    case.domains.append(_domain(sub_id, theme, unit_id, "Department"))
    sub_lead_id = f"{sub_id}_lead"
    heads = case.rng.randint(_LEAD_MIN, _LEAD_MAX)
    skew = _lead_skew(base_skew)
    case.teams.append(_team(sub_lead_id, f"{theme} lead", True, skew, sub_id, heads))
    case.dependencies.append(_dependency(unit_lead_id, sub_lead_id, _LEAD_TO_SUB_DELAY))
    if claimant is not None:
        case.claims.append({"claimant": claimant, "subject": sub_lead_id})
    sub = (sub_id, sub_lead_id)
    parents = _add_groups(case, unit, theme, sub, people - heads)
    _add_leaf_teams(case, unit, theme, sub_id, parents)


def _add_unit_lead(case: _Case, unit) -> tuple[str, int]:
    """Add a unit's leadership team; return its id and the people left over."""
    unit_id, unit_name, population, base_skew, claimant = unit
    if claimant is None:
        heads = _EXEC_HEADCOUNT
        case.teams.append(
            _team("exec", "Group executive", True, _EXEC_SKEW, unit_id, heads)
        )
        return "exec", population - heads
    lead_id = f"{unit_id}_lead"
    heads = case.rng.randint(_LEAD_MIN, _LEAD_MAX)
    skew = _lead_skew(base_skew)
    name = f"{unit_name} leadership"
    case.teams.append(_team(lead_id, name, True, skew, unit_id, heads))
    case.claims.append({"claimant": claimant, "subject": lead_id})
    case.dependencies.append(_dependency("exec", lead_id, _EXEC_TO_UNIT_DELAY))
    return lead_id, population - heads


def _add_cross_unit_edges(case: _Case) -> None:
    """Sample the delayed dependency chain across units at team level."""
    for up_unit, down_unit, delay, count in _CROSS_UNIT_EDGES:
        ups = case.rng.sample(case.delivery[up_unit], count)
        downs = case.rng.sample(case.delivery[down_unit], count)
        for upstream, downstream in zip(ups, downs):
            case.dependencies.append(_dependency(upstream, downstream, delay))


def build() -> dict:
    """Build the whole case as the standard import dictionary."""
    case = _Case(random.Random(_SEED))
    case.domains.append(_domain("company", "Company", None, "Company"))
    for unit in _UNITS:
        unit_id = unit[0]
        themes = _UNIT_THEMES[unit_id]
        case.domains.append(_domain(unit_id, unit[1], "company", "Division"))
        case.delivery[unit_id] = []
        unit_lead_id, remaining = _add_unit_lead(case, unit)
        share, extra = divmod(remaining, len(themes))
        for index, theme in enumerate(themes):
            people = share + (1 if index < extra else 0)
            _add_sub_unit(case, unit, theme, unit_lead_id, people)
    _add_cross_unit_edges(case)
    return {
        "teams": case.teams,
        "dependencies": case.dependencies,
        "workload": _WORKLOAD,
        "origin": "imported",
        "domains": case.domains,
        "claims": case.claims,
        "calibration": _CALIBRATION,
    }


def main() -> int:
    data = build()
    people = sum(team["headcount"] for team in data["teams"])
    if people != TARGET_PEOPLE:
        raise ValueError(f"generated {people} people, expected {TARGET_PEOPLE}")
    org = org_from_dict(data)
    score = evaluate(org, DEFAULT_PARAMETERS)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    print(
        f"wrote {OUTPUT_PATH.name}: {total_headcount(org):,} people, "
        f"{len(data['teams'])} teams, {len(data['domains'])} domains, "
        f"{len(data['dependencies'])} dependencies, {len(data['claims'])} claims"
    )
    print(f"score {score.value:.1f} against band 0..30")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
