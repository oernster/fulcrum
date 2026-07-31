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
     archetype (the canonical blunder stays negative);
  5. imposing a matrix overlay still lowers the score on every typical
     archetype (the contest blunder stays negative).

The three composite penalty weights (latency, escalation, rework) must sum to
1.0 by construction, so each is perturbed and the trio renormalised rather
than perturbed in isolation. Integer parameters (ideal_team_size,
influence_tolerance and the prince band's headcount edges dunbar_headcount
and prince_band_upper) are structural counts, not tuned magnitudes, so they
are outside the sweep; the prince band's float coefficients are inside it.

The axis sweep explores only the edges of the perturbation box; models
typically break in the interior. So a second, joint sweep follows: a Latin
hypercube of draws inside the same box with every coefficient moving at once,
reporting the fraction of draws under which each conclusion holds. Each draw
is renormalised and capped the same way the axis sweep is, so every sampled
configuration respects the constraints SimulationParameters validates.

Both sweeps are deterministic and free of the wall clock: the axis sweep has
no randomness at all and the joint sweep draws from a fixed published seed,
so every run reproduces this output exactly.

Run from the repo root:

    python sensitivity.py
"""

from __future__ import annotations

import json
import random
from dataclasses import replace
from itertools import pairwise
from pathlib import Path

from fulcrum.domain.models import Dependency, OrgState, Origin, Team
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

# The joint sweep: Latin hypercube draws inside the same box, every
# coefficient moving at once. The seed is the published one from the books'
# worked numbers, so the run reproduces exactly.
JOINT_DRAWS = 1000
JOINT_SEED = 20260711

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
# constraint in SimulationParameters.__post_init__. The prince-band floats
# join the sweep; its headcount edges (dunbar_headcount, prince_band_upper)
# are structural counts like the other integers and stay outside it. The
# survivor ceiling is capped against the positive-capacity constraint below.
INDEPENDENT_COEFFICIENTS = (
    "base_capacity",
    "authority_penalty",
    "contested_penalty",
    "coupling_weight",
    "incentive_weight",
    "delay_arrival_weight",
    "cognitive_load_weight",
    "influence_weight",
    "contested_weight",
    "prince_attenuation",
    "prince_amplification",
    "prince_survivor_ceiling",
)

# A perturbed survivor ceiling must keep escalation capacity strictly
# positive: ceiling * (1 - authority_penalty) < 1. The headroom fraction
# keeps the capped value clear of the validated boundary.
PRINCE_CEILING_HEADROOM = 0.99
# The composite penalty weights are constrained to sum to 1.0, so a
# perturbation to one is followed by renormalising all three.
COMPOSITE_WEIGHTS = ("latency_weight", "escalation_weight", "rework_weight")

_APPROVAL_MOVE = Move(MoveKind.ADD_APPROVAL_LAYER)
_OVERLAY_MOVE = Move(MoveKind.IMPOSE_MATRIX_OVERLAY)

# The five qualitative conclusions under test, as (check-result key, label).
CONCLUSIONS = (
    ("typical_order", "typical order holds"),
    ("well_order", "well-designed order holds"),
    ("pairwise", "well-designed > typical pairwise"),
    ("approval_negative", "approval layer stays negative"),
    ("overlay_negative", "matrix overlay stays negative"),
)


def load_org(path: Path) -> OrgState:
    """Build an OrgState from an archetype JSON file (the blueprint shape)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    teams = tuple(
        Team(
            id=t["id"],
            name=t["name"],
            has_local_authority=t["has_local_authority"],
            incentive_skew=t.get("incentive_skew", 0.0),
            headcount=t["headcount"],
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
        scaled = {name: getattr(base, name) * factor}
        # The ceiling constraint couples two coefficients, so whichever of
        # the pair moved, the ceiling is capped against the effective
        # authority penalty.
        authority = scaled.get("authority_penalty", base.authority_penalty)
        ceiling = scaled.get("prince_survivor_ceiling", base.prince_survivor_ceiling)
        scaled["prince_survivor_ceiling"] = min(
            ceiling, PRINCE_CEILING_HEADROOM / (1.0 - authority)
        )
        return replace(base, **scaled)
    raw = {w: getattr(base, w) for w in COMPOSITE_WEIGHTS}
    raw[name] *= factor
    total = sum(raw.values())
    normalised = {w: value / total for w, value in raw.items()}
    return replace(base, **normalised)


def latin_hypercube(
    rng: random.Random, draws: int, dims: int
) -> tuple[tuple[float, ...], ...]:
    """Latin hypercube of factors in [1 - PERTURBATION, 1 + PERTURBATION].

    Each dimension is stratified into `draws` equal bands and every band is
    sampled exactly once, so the interior of the box is covered evenly
    rather than clustered around the centre.
    """
    low = 1.0 - PERTURBATION
    width = 2.0 * PERTURBATION
    columns = []
    for _ in range(dims):
        column = [low + width * (i + rng.random()) / draws for i in range(draws)]
        rng.shuffle(column)
        columns.append(column)
    return tuple(zip(*columns))


def jointly_perturbed(factors: tuple[float, ...]) -> SimulationParameters:
    """DEFAULT_PARAMETERS with every coefficient scaled at once.

    The composite trio is renormalised to its enforced sum of 1.0 and
    contested_penalty is capped at the perturbed authority_penalty, so every
    draw respects the same structural constraints the model validates.
    """
    names = INDEPENDENT_COEFFICIENTS + COMPOSITE_WEIGHTS
    scaled = {
        name: getattr(DEFAULT_PARAMETERS, name) * factor
        for name, factor in zip(names, factors)
    }
    scaled["contested_penalty"] = min(
        scaled["contested_penalty"], scaled["authority_penalty"]
    )
    scaled["prince_survivor_ceiling"] = min(
        scaled["prince_survivor_ceiling"],
        PRINCE_CEILING_HEADROOM / (1.0 - scaled["authority_penalty"]),
    )
    total = sum(scaled[weight] for weight in COMPOSITE_WEIGHTS)
    for weight in COMPOSITE_WEIGHTS:
        scaled[weight] /= total
    return replace(DEFAULT_PARAMETERS, **scaled)


def scores(orgs: tuple[OrgState, ...], params: SimulationParameters) -> tuple:
    return tuple(evaluate(org, params).value for org in orgs)


def strictly_decreasing(values: tuple) -> bool:
    return all(a > b for a, b in pairwise(values))


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
    overlay_deltas = tuple(
        evaluate(apply_move(org, _OVERLAY_MOVE), params).value
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
        "overlay_negative": all(delta < 0 for delta in overlay_deltas),
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
        f"{'well order':>12}{'well>typical':>14}{'approval<0':>12}{'overlay<0':>11}"
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
            holds = all(result[key] for key, _ in CONCLUSIONS)
            all_hold = all_hold and holds
            print(
                f"{name:<24}{factor:>8.1f}"
                f"{flag(result['typical_order']):>15}"
                f"{flag(result['well_order']):>12}"
                f"{flag(result['pairwise']):>14}"
                f"{flag(result['approval_negative']):>12}"
                f"{flag(result['overlay_negative']):>11}"
            )
    print()
    verdict = (
        "All five qualitative conclusions survive every perturbation."
        if all_hold
        else "At least one qualitative conclusion FAILED under perturbation."
    )
    print(verdict)
    print()

    dims = len(INDEPENDENT_COEFFICIENTS + COMPOSITE_WEIGHTS)
    draws = latin_hypercube(random.Random(JOINT_SEED), JOINT_DRAWS, dims)
    held = dict.fromkeys((key for key, _ in CONCLUSIONS), 0)
    all_five = 0
    for factors in draws:
        result = check(typical, well, jointly_perturbed(factors))
        if all(result[key] for key, _ in CONCLUSIONS):
            all_five += 1
        for key, _ in CONCLUSIONS:
            held[key] += result[key]
    print(
        f"Joint sweep (Latin hypercube, {JOINT_DRAWS} draws, every coefficient "
        f"moving at once, seed {JOINT_SEED})"
    )
    print(f"{'conclusion':<36}{'fraction of draws holding':>28}")
    for key, label in CONCLUSIONS:
        print(f"{label:<36}{held[key] / JOINT_DRAWS:>28.1%}")
    print(f"{'all five together':<36}{all_five / JOINT_DRAWS:>28.1%}")
    return 0 if all_hold else 1


if __name__ == "__main__":
    raise SystemExit(main())
