"""Tests for the self-contained HTML plan report."""

from fulcrum.application.plan import build_plan_report
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind, apply_move
from fulcrum.infrastructure.plan_html import render_plan_html


def _org():
    return OrgState(
        teams=(
            Team("a", "Alpha", False, 0.3, domain_id="plat"),
            Team("b", "Bravo", False, 0.5, domain_id="pay"),
        ),
        dependencies=(Dependency("a", "b", 4),),
        workload=6,
        domains=(Domain("plat", "R&D"), Domain("pay", "Payments", lead="Dana")),
    )


def _final(org, moves):
    current = org
    for move in moves:
        current = apply_move(current, move)
    return current


def test_html_is_self_contained_and_addressed_per_domain():
    org = _org()
    moves = (
        Move(MoveKind.DELEGATE_AUTHORITY, ("a",)),
        Move(MoveKind.DELEGATE_AUTHORITY, ("b",)),
        Move(MoveKind.ADD_APPROVAL_LAYER),
    )
    report = build_plan_report(org, moves, DeterministicSimulator())
    html = render_plan_html(report, org, _final(org, moves), "2026-06-18T10:00:00")
    assert html.startswith("<!DOCTYPE html>")
    assert html.count("<svg") >= 2
    assert "Generated 2026-06-18T10:00:00" in html
    assert "Payments (for Dana)" in html
    assert "R&amp;D (for the domain lead)" in html
    assert "Organisation-wide moves (held by the CTO)" in html
    assert "Structural health" in html
    # A single-history report keeps the plain look: no record to separate.
    assert 'class="historic"' not in html
    assert 'class="current"' not in html
    assert "moves from earlier runs" not in html


def test_html_carries_the_frame_verdict_for_local_moves():
    org = _org()
    moves = (Move(MoveKind.DELEGATE_AUTHORITY, ("a",)),)
    report = build_plan_report(org, moves, DeterministicSimulator())
    html = render_plan_html(report, org, _final(org, moves), "2026-06-18T10:00:00")
    assert 'class="local"' in html
    assert "within <b>R&amp;D</b>: section health" in html
    assert "Each move carries two verdicts" in html


def test_html_omits_the_frame_verdict_for_org_wide_plans():
    org = _org()
    moves = (Move(MoveKind.ADD_APPROVAL_LAYER),)
    report = build_plan_report(org, moves, DeterministicSimulator())
    html = render_plan_html(report, org, _final(org, moves), "2026-06-18T10:00:00")
    assert 'class="local"' not in html
    assert "Each move carries two verdicts" not in html


def test_html_separates_earlier_runs_from_this_run():
    org = _org()
    moves = (
        Move(MoveKind.DELEGATE_AUTHORITY, ("a",)),
        Move(MoveKind.DELEGATE_AUTHORITY, ("b",)),
    )
    report = build_plan_report(org, moves, DeterministicSimulator(), prior_moves=1)
    html = render_plan_html(report, org, _final(org, moves), "2026-06-18T10:00:00")
    assert html.count('<li class="historic">') == 1
    assert html.count('<li class="current">') == 1
    assert "moves from earlier runs" in html
    assert "moves from this run" in html
    assert "1 move from earlier runs, 1 move this run." in html
