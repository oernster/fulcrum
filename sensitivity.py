#!/usr/bin/env python3
"""Sensitivity sweep over the scoring coefficients, on the published archetypes.

Perturbs every tunable coefficient in SimulationParameters by a fixed fraction
in each direction, re-scores the ten shipped archetypes (the five typical
organisations in examples/ and their five well-designed counterparts) and
reports whether the qualitative conclusions survive:

  1. the typical archetypes still rank startup > scale-up > enterprise >
     very large > conglomerate;
  2. the well-designed archetypes keep the same rank order;
  3. every well-designed archetype still outscores its typical counterpart;
  4. adding an approval layer still lowers the score on every typical
     archetype (the canonical blunder stays negative).

The three composite penalty weights (latency, escalation, rework) must sum to
1.0 by construction, so each is perturbed and the trio renormalised rather
than perturbed in isolation. Integer parameters (ideal_team_size,
influence_tolerance) are structural counts, not tuned magnitudes, so they are
outside the sweep. The sweep is deterministic: no randomness, no wall clock.

Run from the repo root:

    python sensitivity.py
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from fulcrum.domain.models import Dependency, Origin, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind, apply_move
from fulcrum.domain.simulation import (
    DEFAULT_PARAMETERS,
    SimulationParameters,
    evaluate,
)

ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / "examples"
WELL_DESIGNED_DIR = EXAMPLES / "well-designed"

# The perturbation applied to each coefficient, as a fraction of its default.
PERTURBATION = 0.2
FACTORS = (1.0 - PERTURBATION, 1.0 + PERTURBATION)

# The archetypes, smallest organisation first. The published claim under test
# is that the typical column collapses with scale while the well-designed
# column degrades gently, so rank order within each column is the invariant.
ARCHETYPE_LABELS = (
    "startup",
    "scale-up",
    "enterprise",
    "very large",
    "conglomerate",
)
TYPICAL_FILES = (
    "org-1-startup.json",
    "org-2-scaleup.json",
    "org-3-enterprise.json",
    "org-4-very-large.json",
    "org-5-conglomerate.json",
)
WELL_DESIGNED_FILES = (
    "startup.json",
    "scaleup.json",
    "enterprise.json",
    "very-large.json",
    "conglomerate.json",
)

# Coefficients that can move independently without violating a validation
# constraint in SimulationParameters.__post_init__.
INDEPENDENT_COEFFICIENTS = (
    "base_capacity",
    "authority_penalty",
    "coupling_weight",
    "incentive_weight",
    "delay_arrival_weight",
    "cognitive_load_weight",
    "influence_weight",
)
# The composite penalty weights are constrained to sum to 1.0, so a
# perturbation to one is followed by renormalising all three.
COMPOSITE_WEIGHTS = ("latency_weight", "escalation_weight", "rework_weight")

_APPROVAL_MOVE = Move(MoveKind.ADD_APPROVAL_LAYER)


def load_org(path: Path) -> OrgState:
    """Build an OrgState from an archetype JSON file (the blueprint shape)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    teams = tuple(
        Team(
            id=t["id"],
            name=t["name"],
            has_local_authority=t["has_local_authority"],
            incentive_skew=t.get("incentive_skew", 0.0),
        )
        for t in data["teams"]
    )
    dependencies = tuple(
        Dependency(d["upstream"], d["downstream"], d["propagation_delay"])
        for d in data["dependencies"]
    )
    return OrgState(
        teams=teams,
        dependencies=dependencies,
        workload=data["workload"],
        origin=Origin.IMPORTED,
    )


def perturbed(name: str, factor: float) -> SimulationParameters:
    """DEFAULT_PARAMETERS with one coefficient scaled by factor.

    A composite weight is scaled then the trio renormalised so the validated
    sum-to-one constraint holds; every other coefficient moves alone.
    """
    base = DEFAULT_PARAMETERS
    if name in INDEPENDENT_COEFFICIENTS:
        return replace(base, **{name: getattr(base, name) * factor})
    raw = {w: getattr(base, w) for w in COMPOSITE_WEIGHTS}
    raw[name] *= factor
    total = sum(raw.values())
    normalised = {w: value / total for w, value in raw.items()}
    return replace(base, **normalised)


def scores(orgs: tuple[OrgState, ...], params: SimulationParameters) -> tuple:
    return tuple(evaluate(org, params).value for org in orgs)


def strictly_decreasing(values: tuple) -> bool:
    return all(a > b for a, b in zip(values, values[1:]))


def check(
    typical: tuple[OrgState, ...],
    well: tuple[OrgState, ...],
    params: SimulationParameters,
) -> dict:
    """Score both columns under params and test the four invariants."""
    typical_scores = scores(typical, params)
    well_scores = scores(well, params)
    approval_deltas = tuple(
        evaluate(apply_move(org, _APPROVAL_MOVE), params).value
        - evaluate(org, params).value
        for org in typical
    )
    return {
        "typical": typical_scores,
        "well": well_scores,
        "typical_order": strictly_decreasing(typical_scores),
        "well_order": strictly_decreasing(well_scores),
        "pairwise": all(w > t for w, t in zip(well_scores, typical_scores)),
        "approval_negative": all(delta < 0 for delta in approval_deltas),
        "worst_approval_delta": max(approval_deltas),
    }


def flag(ok: bool) -> str:
    return "yes" if ok else "NO"


def main() -> int:
    typical = tuple(load_org(EXAMPLES / name) for name in TYPICAL_FILES)
    well = tuple(load_org(WELL_DESIGNED_DIR / name) for name in WELL_DESIGNED_FILES)

    baseline = check(typical, well, DEFAULT_PARAMETERS)
    print("Baseline scores (default coefficients)")
    print(f"{'archetype':<14}{'typical':>10}{'well-designed':>16}")
    for label, t, w in zip(ARCHETYPE_LABELS, baseline["typical"], baseline["well"]):
        print(f"{label:<14}{t:>10.1f}{w:>16.1f}")
    print()

    header = (
        f"{'coefficient':<24}{'factor':>8}{'typical order':>15}"
        f"{'well order':>12}{'well>typical':>14}{'approval<0':>12}"
    )
    print(
        f"Perturbation sweep (each coefficient scaled by {FACTORS[0]:.1f} "
        f"and {FACTORS[1]:.1f})"
    )
    print(header)
    all_hold = True
    for name in INDEPENDENT_COEFFICIENTS + COMPOSITE_WEIGHTS:
        for factor in FACTORS:
            result = check(typical, well, perturbed(name, factor))
            holds = (
                result["typical_order"]
                and result["well_order"]
                and result["pairwise"]
                and result["approval_negative"]
            )
            all_hold = all_hold and holds
            print(
                f"{name:<24}{factor:>8.1f}"
                f"{flag(result['typical_order']):>15}"
                f"{flag(result['well_order']):>12}"
                f"{flag(result['pairwise']):>14}"
                f"{flag(result['approval_negative']):>12}"
            )
    print()
    verdict = (
        "All four qualitative conclusions survive every perturbation."
        if all_hold
        else "At least one qualitative conclusion FAILED under perturbation."
    )
    print(verdict)
    return 0 if all_hold else 1


if __name__ == "__main__":
    raise SystemExit(main())
