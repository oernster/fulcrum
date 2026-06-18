"""Tests for the domain-hierarchy queries and focused sub-org views."""

from fulcrum.domain import hierarchy
from fulcrum.domain.models import Dependency, Domain, OrgState, Team


def _org():
    return OrgState(
        teams=(
            Team("a", "A", True, 0.0, domain_id="plat"),
            Team("b", "B", False, 0.2, domain_id="pay"),
            Team("c", "C", True, 0.0, domain_id="pay"),
            Team("d", "D", True, 0.0, domain_id=None),
        ),
        dependencies=(
            Dependency("a", "b", 2),
            Dependency("b", "c", 1),
            Dependency("c", "d", 3),
        ),
        workload=5,
        domains=(
            Domain("plat", "Platform"),
            Domain("pay", "Payments", parent_id="plat"),
        ),
    )


def test_root_and_child_domains():
    org = _org()
    assert tuple(d.id for d in hierarchy.root_domains(org)) == ("plat",)
    assert tuple(d.id for d in hierarchy.child_domains(org, "plat")) == ("pay",)


def test_subtree_and_teams_recursive_vs_direct():
    org = _org()
    assert hierarchy.domain_subtree_ids(org, "plat") == frozenset({"plat", "pay"})
    assert hierarchy.domain_subtree_ids(org, "pay") == frozenset({"pay"})
    recursive = {t.id for t in hierarchy.teams_in_domain(org, "plat")}
    assert recursive == {"a", "b", "c"}
    direct = {t.id for t in hierarchy.teams_in_domain(org, "plat", recursive=False)}
    assert direct == {"a"}


def test_domain_has_teams():
    org = _org()
    assert hierarchy.domain_has_teams(org, "pay") is True
    empty = OrgState(
        teams=(Team("a", "A", True, 0.0, domain_id="x"),),
        domains=(Domain("x", "X"), Domain("y", "Y")),
    )
    assert hierarchy.domain_has_teams(empty, "y") is False


def test_focused_suborg_flattens_and_keeps_internal_deps():
    focus = hierarchy.focused_suborg(_org(), "pay")
    assert {t.id for t in focus.teams} == {"b", "c"}
    assert all(t.domain_id is None for t in focus.teams)
    assert focus.domains == ()
    pairs = sorted((d.upstream, d.downstream) for d in focus.dependencies)
    assert pairs == [("b", "c")]
    assert focus.workload == 5


def test_boundary_dependencies_are_the_cross_domain_surface():
    pairs = sorted(
        (d.upstream, d.downstream)
        for d in hierarchy.boundary_dependencies(_org(), "pay")
    )
    assert pairs == [("a", "b"), ("c", "d")]
