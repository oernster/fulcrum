#!/usr/bin/env python3
"""Score the calibration organisations against their expected bands.

Each JSON file in examples/calibration/ (except TEMPLATE.json) is an org in
the standard import shape plus a "calibration" block:

    "calibration": {
        "label": "Fintech scale-up, 2019",
        "expected_min": 40,
        "expected_max": 70,
        "note": "shipped, but every quarter ended in a crunch"
    }

The runner scores every case with the default coefficients, prints the
score beside the expected band and the penalty decomposition, and exits
non-zero when any case lands outside its band. It is deterministic: same
files, same numbers.

Calibration cases are modelled WITH knowledge of their outcomes, including
cases from lived experience. They tune the prior and are therefore
permanently ineligible for the preregistered blind validation
(PREREGISTRATION.md): never promote a calibration case into that set.

Run from the repo root:

    python calibrate.py
"""

from __future__ import annotations

import json
from pathlib import Path

from fulcrum.domain.hierarchy import total_headcount
from fulcrum.domain.simulation import (
    DEFAULT_PARAMETERS,
    evaluate,
    frame_headcount,
    prince_scale_factor,
)
from fulcrum.infrastructure.json_serialization import org_from_dict

ROOT = Path(__file__).resolve().parent
CALIBRATION_DIR = ROOT / "examples" / "calibration"
TEMPLATE_NAME = "TEMPLATE.json"


def run() -> int:
    cases = sorted(
        path for path in CALIBRATION_DIR.glob("*.json") if path.name != TEMPLATE_NAME
    )
    if not cases:
        print(f"No calibration cases found in {CALIBRATION_DIR}.")
        return 1
    header = (
        f"{'case':<34}{'people':>8}{'score':>8}{'band':>12}{'verdict':>9}"
        f"{'lat':>7}{'esc':>7}{'rew':>7}{'factor':>8}"
    )
    print(header)
    print("-" * len(header))
    misses = 0
    for path in cases:
        data = json.loads(path.read_text(encoding="utf-8"))
        meta = data["calibration"]
        org = org_from_dict(data)
        score = evaluate(org, DEFAULT_PARAMETERS)
        low, high = meta["expected_min"], meta["expected_max"]
        inside = low <= score.value <= high
        misses += 0 if inside else 1
        factor = prince_scale_factor(frame_headcount(org), DEFAULT_PARAMETERS)
        print(
            f"{meta['label']:<34}{total_headcount(org):>8,}"
            f"{score.value:>8.1f}{f'{low}..{high}':>12}"
            f"{'PASS' if inside else 'MISS':>9}"
            f"{score.latency_penalty:>7.2f}{score.escalation_penalty:>7.2f}"
            f"{score.rework_penalty:>7.2f}{factor:>8.2f}"
        )
        note = meta.get("note", "")
        if note:
            print(f"    {note}")
    print()
    if misses:
        print(f"{misses} case(s) outside their expected band.")
        return 1
    print("Every calibration case sits inside its expected band.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
