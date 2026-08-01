"""Tests for the plan report: scoring, attribution, rationale and grouping."""

from dataclasses import replace

from fulcrum.application.plan import _best_easing, build_plan_report
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.hierarchy import focused_suborg
from fulcrum.domain.models import AuthorityClaim, Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind, apply_move
from fulcrum.domain.signals import ESCALATIONS, QUEUE_AGE, compute_signals


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


def _nested_org():
    return OrgState(
        teams=(
            Team("a", "Alpha", False, 0.3, domain_id="plat"),
            Team("b", "Bravo", False, 0.5, domain_id="plat"),
            Team("c", "Card", False, 0.4, domain_id="pay"),
            Team("u", "Solo", False, 0.4, domain_id=None),
        ),
        dependencies=(Dependency("a", "b", 4), Dependency("a", "c", 4)),
        workload=7,
        domains=(
            Domain("eng", "Engineering"),
            Domain("plat", "Platform", parent_id="eng"),
            Domain("pay", "Payments", parent_id="eng"),
        ),
        claims=(AuthorityClaim("Steering", "b"),),
    )


def test_local_verdict_follows_the_moves_own_frame():
    moves = (
        Move(MoveKind.DELEGATE_AUTHORITY, ("a",)),
        Move(MoveKind.COLLAPSE_BOUNDARY, ("a", "c")),
        Move(MoveKind.STABILISE_INTERFACES, ("plat", "pay")),
        Move(MoveKind.DOWNGRADE_CLAIM, ("Steering", "b")),
        Move(MoveKind.DELEGATE_AUTHORITY, ("u",)),
        Move(MoveKind.ADD_APPROVAL_LAYER),
    )
    report = build_plan_report(_nested_org(), moves, DeterministicSimulator())
    frames = [step.local for step in report.steps]
    # a sits inside Platform; a + c share only Engineering; a scoped
    # stabilise names frame nodes and lands in their shared parent; an
    # unmodelled claimant contributes nothing so the subject locates the
    # downgrade; a loose team and an org-wide act carry no frame at all.
    assert frames[0] is not None and frames[0].frame_label == "Platform"
    assert frames[1] is not None and frames[1].frame_label == "Engineering"
    assert frames[2] is not None and frames[2].frame_label == "Engineering"
    assert frames[3] is not None and frames[3].frame_label == "Platform"
    assert frames[4] is None
    assert frames[5] is None


def test_local_scores_are_the_frames_own_scores():
    org = _nested_org()
    move = Move(MoveKind.DELEGATE_AUTHORITY, ("a",))
    simulator = DeterministicSimulator()
    report = build_plan_report(org, (move,), simulator)
    local = report.steps[0].local
    after = apply_move(org, move)
    assert local.score_before == simulator.score(focused_suborg(org, "plat")).value
    assert local.score_after == simulator.score(focused_suborg(after, "plat")).value


def test_easing_ignores_falls_invisible_at_display_precision():
    reading = next(r for r in compute_signals(_org()) if r.definition.key == QUEUE_AGE)
    before = (replace(reading, value=215.84),)
    after = (replace(reading, value=215.79),)
    assert _best_easing(before, after) is None


def test_easing_picks_the_biggest_visible_fall():
    readings = compute_signals(_org())
    queue = next(r for r in readings if r.definition.key == QUEUE_AGE)
    escalations = next(r for r in readings if r.definition.key == ESCALATIONS)
    before = (replace(queue, value=215.84), replace(escalations, value=5.0))
    after = (replace(queue, value=215.79), replace(escalations, value=4.0))
    best = _best_easing(before, after)
    assert best is not None
    assert best[0].definition.key == ESCALATIONS


def test_prior_moves_mark_the_record_as_historic():
    moves = (
        Move(MoveKind.DELEGATE_AUTHORITY, ("a",)),
        Move(MoveKind.DELEGATE_AUTHORITY, ("b",)),
    )
    report = build_plan_report(_org(), moves, DeterministicSimulator(), prior_moves=1)
    assert [step.historic for step in report.steps] == [True, False]
    plain = build_plan_report(_org(), moves, DeterministicSimulator())
    assert all(step.historic is False for step in plain.steps)
