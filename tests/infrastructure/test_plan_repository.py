"""Tests for plan file export and import."""

from fulcrum.application.dto import Plan
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind
from fulcrum.infrastructure.plan_repository import read_plan, write_html, write_plan


def _plan():
    org = OrgState(
        teams=(
            Team("a", "A", True, 0.1, domain_id="d1"),
            Team("b", "B", False, 0.4, domain_id="d1"),
        ),
        dependencies=(Dependency("a", "b", 3),),
        workload=4,
        domains=(Domain("d1", "Core", lead="Dana"),),
    )
    return Plan(
        initial_org=org,
        moves=(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)),),
        created_at="2026-06-18T00:00:00",
    )


def test_write_then_read_plan_roundtrips(tmp_path):
    plan = _plan()
    path = tmp_path / "sub" / "plan.json"
    write_plan(path, plan)
    loaded = read_plan(path)
    assert loaded.initial_org == plan.initial_org
    assert loaded.moves == plan.moves
    assert loaded.created_at == plan.created_at


def test_write_html_writes_the_file(tmp_path):
    path = tmp_path / "out" / "report.html"
    write_html(path, "<html>ok</html>")
    assert path.read_text(encoding="utf-8") == "<html>ok</html>"
