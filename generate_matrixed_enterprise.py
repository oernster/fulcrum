#!/usr/bin/env python3
"""Regenerate the matrixed-enterprise calibration case.

The case models a ~6,000-person organisation as a real drillable hierarchy:
the company roof holds a leadership unit plus seven delivery units, each unit
holds sub-units, an oversized sub-unit splits into led groups and every leaf
holds a handful of teams of three to eight people with varied sizes, so no
lead anywhere coordinates more than a sane span. Line lead teams (unit,
sub-unit and group) hold local authority on paper but the matrix overlay (a
programme office and an engineering chapter, both unmodelled claimants)
claims every one of them, so no decision class in the delivery organisation
resolves cleanly and queues cascade toward the one clean executive team.
Cross-unit dependencies carry the original case's delayed chain at team
level.

The generator is deterministic: the same seed writes byte-identical JSON, so
the committed case is reproducible from this script alone. Run it from the
repository root after any change, then re-score:

    python generate_matrixed_enterprise.py
    python calibrate.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from fulcrum.domain.hierarchy import total_headcount
from fulcrum.domain.simulation import DEFAULT_PARAMETERS, evaluate
from fulcrum.infrastructure.json_serialization import org_from_dict

ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = ROOT / "examples" / "calibration" / "matrixed-enterprise.json"

_SEED = 20260731
_WORKLOAD = 6
_TARGET_PEOPLE = 6_000

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

# A sub-unit bigger than this splits into groups, each with its own lead
# and a handful of teams: one lead coordinating thirty-odd teams in a flat
# leaf is not a hierarchy, it is a queue wearing one's clothes, and the
# case models a drillable organisation, not a caricature.
_MAX_LEAF_PEOPLE = 45

_PMO = "pmo"
_CHAPTER_ENG = "chapter_eng"

# One entry per unit: id, name, population, baseline incentive skew, the
# matrix claimant on its line leadership (None keeps the leadership clean)
# and its sub-unit themes. Populations and skews carry the original flat
# case's numbers down onto real teams.
_UNITS = (
    (
        "leadership",
        "Group leadership",
        200,
        0.3,
        None,
        ("Programme office", "Engineering chapters"),
    ),
    (
        "core",
        "Core product",
        1200,
        0.4,
        _PMO,
        ("Checkout", "Catalogue", "Search", "Mobile", "Web", "Growth", "Onboarding"),
    ),
    (
        "platform",
        "Platform",
        900,
        0.5,
        _CHAPTER_ENG,
        ("API", "Runtime", "Developer experience", "Messaging", "Storage"),
    ),
    (
        "payments",
        "Payments",
        800,
        0.4,
        _PMO,
        ("Cards", "Ledger", "Payouts", "Risk", "Reconciliation"),
    ),
    (
        "data",
        "Data",
        700,
        0.6,
        _CHAPTER_ENG,
        ("Analytics", "Pipelines", "Reporting", "ML platform"),
    ),
    (
        "infra",
        "Infrastructure",
        800,
        0.5,
        _CHAPTER_ENG,
        ("Compute", "Networking", "Databases", "Observability", "Security ops"),
    ),
    (
        "intl",
        "International",
        900,
        0.5,
        _PMO,
        ("EMEA", "APAC", "LATAM", "Localisation", "Compliance"),
    ),
    (
        "qa",
        "Quality",
        500,
        0.7,
        _PMO,
        ("Test engineering", "Release", "Automation"),
    ),
)

# The original case's delayed dependency chain, kept at unit granularity in
# the story and realised as sampled team-level edges: upstream unit,
# downstream unit, propagation delay, number of team pairs.
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
        "matrix overlay on a delayed dependency chain; " "the documented-collapse shape"
    ),
}


def _slug(theme: str) -> str:
    return theme.lower().replace(" ", "_")


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
    return {
        "upstream": upstream,
        "downstream": downstream,
        "propagation_delay": delay,
    }


def build() -> dict:
    """Build the whole case as the standard import dictionary."""
    rng = random.Random(_SEED)
    teams: list[dict] = []
    domains: list[dict] = [_domain("company", "Company", None, "Company")]
    dependencies: list[dict] = []
    claims: list[dict] = []
    delivery_by_unit: dict[str, list[str]] = {}
    for unit_id, unit_name, population, base_skew, claimant, themes in _UNITS:
        domains.append(_domain(unit_id, unit_name, "company", "Division"))
        delivery_by_unit[unit_id] = []
        if claimant is None:
            unit_lead_id = "exec"
            teams.append(
                _team(
                    unit_lead_id,
                    "Group executive",
                    True,
                    _EXEC_SKEW,
                    unit_id,
                    _EXEC_HEADCOUNT,
                )
            )
            remaining = population - _EXEC_HEADCOUNT
        else:
            unit_lead_id = f"{unit_id}_lead"
            lead_heads = rng.randint(_LEAD_MIN, _LEAD_MAX)
            teams.append(
                _team(
                    unit_lead_id,
                    f"{unit_name} leadership",
                    True,
                    _lead_skew(base_skew),
                    unit_id,
                    lead_heads,
                )
            )
            claims.append({"claimant": claimant, "subject": unit_lead_id})
            dependencies.append(_dependency("exec", unit_lead_id, _EXEC_TO_UNIT_DELAY))
            remaining = population - lead_heads
        share, extra = divmod(remaining, len(themes))
        for index, theme in enumerate(themes):
            sub_population = share + (1 if index < extra else 0)
            sub_id = f"{unit_id}_{_slug(theme)}"
            domains.append(_domain(sub_id, theme, unit_id, "Department"))
            sub_lead_id = f"{sub_id}_lead"
            sub_lead_heads = rng.randint(_LEAD_MIN, _LEAD_MAX)
            teams.append(
                _team(
                    sub_lead_id,
                    f"{theme} lead",
                    True,
                    _lead_skew(base_skew),
                    sub_id,
                    sub_lead_heads,
                )
            )
            dependencies.append(
                _dependency(unit_lead_id, sub_lead_id, _LEAD_TO_SUB_DELAY)
            )
            if claimant is not None:
                claims.append({"claimant": claimant, "subject": sub_lead_id})
            remaining_sub = sub_population - sub_lead_heads
            group_count = -(-remaining_sub // _MAX_LEAF_PEOPLE)
            if group_count == 1:
                parents = [(sub_id, sub_lead_id, remaining_sub)]
            else:
                # An oversized sub-unit splits into led groups, so every
                # leaf keeps a handful of teams under a lead with a sane
                # span instead of dozens hanging off one hub.
                parents = []
                group_share, group_extra = divmod(remaining_sub, group_count)
                for group in range(1, group_count + 1):
                    group_people = group_share + (1 if group <= group_extra else 0)
                    group_id = f"{sub_id}_g{group}"
                    domains.append(
                        _domain(
                            group_id, f"{theme} group {group}", sub_id, "Department"
                        )
                    )
                    group_lead_id = f"{group_id}_lead"
                    group_lead_heads = rng.randint(_LEAD_MIN, _LEAD_MAX)
                    teams.append(
                        _team(
                            group_lead_id,
                            f"{theme} group {group} lead",
                            True,
                            _lead_skew(base_skew),
                            group_id,
                            group_lead_heads,
                        )
                    )
                    dependencies.append(
                        _dependency(sub_lead_id, group_lead_id, _SUB_TO_GROUP_DELAY)
                    )
                    if claimant is not None:
                        # The matrix claims line leadership all the way
                        # down: a group lead is as dual-reported as the
                        # sub-unit lead above it.
                        claims.append({"claimant": claimant, "subject": group_lead_id})
                    parents.append(
                        (group_id, group_lead_id, group_people - group_lead_heads)
                    )
            number = 0
            for parent_id, parent_lead_id, people in parents:
                for heads in _team_sizes(rng, people):
                    number += 1
                    team_id = f"{sub_id}_t{number}"
                    teams.append(
                        _team(
                            team_id,
                            f"{theme} team {number}",
                            False,
                            _skew(rng, base_skew),
                            parent_id,
                            heads,
                        )
                    )
                    dependencies.append(
                        _dependency(parent_lead_id, team_id, _SUB_TO_TEAM_DELAY)
                    )
                    delivery_by_unit[unit_id].append(team_id)
    for up_unit, down_unit, delay, count in _CROSS_UNIT_EDGES:
        ups = rng.sample(delivery_by_unit[up_unit], count)
        downs = rng.sample(delivery_by_unit[down_unit], count)
        for upstream, downstream in zip(ups, downs):
            dependencies.append(_dependency(upstream, downstream, delay))
    return {
        "teams": teams,
        "dependencies": dependencies,
        "workload": _WORKLOAD,
        "origin": "imported",
        "domains": domains,
        "claims": claims,
        "calibration": _CALIBRATION,
    }


def main() -> int:
    data = build()
    people = sum(team["headcount"] for team in data["teams"])
    if people != _TARGET_PEOPLE:
        raise ValueError(f"generated {people} people, expected {_TARGET_PEOPLE}")
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
