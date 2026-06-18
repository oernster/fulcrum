"""Tests for the file plan exporter (HTML report + JSON source)."""

from fulcrum.application.dto import Plan
from fulcrum.application.plan import build_plan_report
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind, apply_move
from fulcrum.infrastructure.plan_exporter import FilePlanExporter
from fulcrum.infrastructure.plan_repository import read_plan


def test_export_writes_report_and_reimportable_source(tmp_path):
    org = OrgState(
        teams=(
            Team("a", "A", False, 0.2, domain_id="d1"),
            Team("b", "B", False, 0.3, domain_id="d1"),
        ),
        dependencies=(Dependency("a", "b", 3),),
        workload=5,
        domains=(Domain("d1", "Core", lead="Dana"),),
    )
    moves = (Move(MoveKind.DELEGATE_AUTHORITY, ("a",)),)
    final = apply_move(org, moves[0])
    report = build_plan_report(org, moves, DeterministicSimulator())
    plan = Plan(org, moves, "2026-06-18T00:00:00")
    html_path = tmp_path / "plan.html"

    FilePlanExporter().export(
        str(html_path), report, plan, final, "2026-06-18T00:00:00"
    )

    assert html_path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    json_path = html_path.with_suffix(".json")
    assert json_path.exists()
    assert read_plan(json_path).moves == moves

    reloaded = FilePlanExporter().read(str(json_path))
    assert reloaded.moves == moves
    assert reloaded.initial_org == org
