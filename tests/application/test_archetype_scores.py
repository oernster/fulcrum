"""Golden test: the shipped archetypes keep their published scores.

The site publishes these numbers (why.html and model.html), so any model
change that moves them must be deliberate and update the site in the same
change. The archetypes carry real headcounts, so the typical column is
priced through the prince band while the well-designed column, holding no
concentrated authority and no claims, keeps the scores it had before the
band existed: the scale rule prices concentration only.
"""

import json
from pathlib import Path

import pytest

from fulcrum.domain.models import Dependency, OrgState, Origin, Team
from fulcrum.domain.simulation import evaluate

_EXAMPLES = Path(__file__).resolve().parents[2] / "examples"

_PUBLISHED = (
    ("org-1-startup.json", "well-designed/startup.json", 90.6, 98.7),
    ("org-2-scaleup.json", "well-designed/scaleup.json", 47.8, 91.0),
    ("org-3-enterprise.json", "well-designed/enterprise.json", 17.2, 78.7),
    ("org-4-very-large.json", "well-designed/very-large.json", 12.2, 68.8),
    ("org-5-conglomerate.json", "well-designed/conglomerate.json", 8.8, 66.4),
)


def _load(relative: str) -> OrgState:
    data = json.loads((_EXAMPLES / relative).read_text(encoding="utf-8"))
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


@pytest.mark.parametrize("typical, well, typical_score, well_score", _PUBLISHED)
def test_archetype_scores_match_the_published_numbers(
    typical, well, typical_score, well_score
):
    assert round(evaluate(_load(typical)).value, 1) == typical_score
    assert round(evaluate(_load(well)).value, 1) == well_score
