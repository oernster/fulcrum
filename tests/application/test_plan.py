"""Tests for the plan report: scoring, attribution, rationale and grouping."""

from fulcrum.application.plan import build_plan_report
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind


def _org():
    return OrgState(
        teams=(
            Team("a", "Alpha", False, 0.3, domain_id="plat"),
            Team("b", "Bravo", False, 0.5, domain_id="pay"),
            Team("u", "Solo", False, 0.4, domain_id=None),
        ),
        dependencies=(Dependency("a", "b", 4), Dependency("b", "u", 4)),
        workload=7,
        domains=(
            Domain("plat", "Platform"),
            Domain("pay", "Payments", lead="Dana"),
        ),
    )


_MOVES = (
    Move(MoveKind.DELEGATE_AUTHORITY, ("a",)),
    Move(MoveKind.DELEGATE_AUTHORITY, ("b",)),
    Move(MoveKind.REALIGN_INCENTIVES, ("b",)),
    Move(MoveKind.DELEGATE_AUTHORITY, ("u",)),
    Move(MoveKind.STABILISE_INTERFACES),
    Move(MoveKind.ADD_APPROVAL_LAYER),
)


def test_report_scores_attributes_and_justifies_each_step():
    report = build_plan_report(_org(), _MOVES, DeterministicSimulator())
    assert len(report.steps) == len(_MOVES)
    assert report.final_score == report.steps[-1].score_after
    assert report.steps[0].domain_id == "plat"
    assert report.steps[1].domain_id == "pay"
    # an unassigned-team move, stabilise and approval all fall to the CTO
    assert report.steps[3].domain_id is None
    assert report.steps[4].domain_id is None
    assert report.steps[5].domain_id is None
    # a delegating move eases a signal; the approval blunder only moves health
    assert "falls" in report.steps[0].rationale
    assert "structural health" in report.steps[5].rationale


def test_recommendations_group_by_domain_and_carry_the_lead():
    report = build_plan_report(_org(), _MOVES, DeterministicSimulator())
    by_id = {rec.domain_id: rec for rec in report.recommendations}
    assert set(by_id) == {"plat", "pay", None}
    assert len(by_id["pay"].steps) == 2
    assert by_id["pay"].lead == "Dana"
    assert by_id[None].label == "Organisation-wide (CTO)"
    assert by_id[None].lead == ""


def test_rationale_states_health_only_when_no_signal_eases():
    org = OrgState(
        teams=(Team("a", "A", True, 0.0), Team("b", "B", True, 0.0)),
        dependencies=(Dependency("a", "b", 0),),
        workload=1,
    )
    report = build_plan_report(
        org, (Move(MoveKind.STABILISE_INTERFACES),), DeterministicSimulator()
    )
    assert "structural health" in report.steps[0].rationale
    assert "falls" not in report.steps[0].rationale


def test_empty_plan_reports_the_start_score_only():
    org = _org()
    report = build_plan_report(org, (), DeterministicSimulator())
    assert report.steps == ()
    assert report.recommendations == ()
    assert report.final_score == report.start_score
