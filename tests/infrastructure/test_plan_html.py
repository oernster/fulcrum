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
