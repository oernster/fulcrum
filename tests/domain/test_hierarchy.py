"""Tests for the domain-hierarchy queries and focused sub-org views."""

from fulcrum.domain import hierarchy
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind


def _nested_org():
    return OrgState(
        teams=(
            Team("a", "A", False, 0.8, domain_id="d1"),
            Team("b", "B", False, 0.6, domain_id="d1"),
            Team("c", "C", True, 0.2, domain_id="d2"),
            Team("e", "E", True, 0.1, domain_id="d2"),
        ),
        dependencies=(Dependency("a", "b", 4), Dependency("b", "c", 2)),
        workload=3,
        domains=(
            Domain("root", "Org"),
            Domain("d1", "Dept One", parent_id="root"),
            Domain("d2", "Dept Two", parent_id="root"),
        ),
    )


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
    assert tuple(d.id for d in hierarchy.child_domains(org, None)) == ("plat",)


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


def test_focused_suborg_aggregates_a_non_leaf_into_child_nodes():
    focus = hierarchy.focused_suborg(_nested_org(), "root")
    nodes = {t.id: t for t in focus.teams}
    assert set(nodes) == {"d1", "d2"}
    assert nodes["d1"].has_local_authority is False
    assert nodes["d2"].has_local_authority is True
    assert nodes["d1"].incentive_skew == 0.7
    assert nodes["d2"].incentive_skew == 0.15
    assert [(d.upstream, d.downstream) for d in focus.dependencies] == [("d1", "d2")]


def test_focused_suborg_skips_a_childless_empty_branch():
    org = OrgState(
        teams=(Team("a", "A", True, 0.0, domain_id="d1"),),
        domains=(
            Domain("root", "Org"),
            Domain("d1", "Has teams", parent_id="root"),
            Domain("d2", "Empty", parent_id="root"),
        ),
    )
    focus = hierarchy.focused_suborg(org, "root")
    assert {t.id for t in focus.teams} == {"d1"}


def test_translate_focused_move_expands_to_subtree_teams():
    real = hierarchy.translate_focused_move(
        _nested_org(), "root", Move(MoveKind.DELEGATE_AUTHORITY, ("d1",))
    )
    assert real.kind == MoveKind.DELEGATE_AUTHORITY
    assert set(real.targets) == {"a", "b"}


def test_translate_focused_move_passes_through_leaf_and_global():
    org = _nested_org()
    leaf_move = Move(MoveKind.DELEGATE_AUTHORITY, ("a",))
    assert hierarchy.translate_focused_move(org, "d1", leaf_move) is leaf_move
    assert hierarchy.translate_focused_move(org, None, leaf_move) is leaf_move
    stabilise = Move(MoveKind.STABILISE_INTERFACES)
    assert hierarchy.translate_focused_move(org, "root", stabilise) is stabilise


def test_headcount_rolls_up_through_the_domain_subtree():
    org = OrgState(
        teams=(
            Team("a", "A", True, 0.0, domain_id="plat", headcount=10),
            Team("b", "B", True, 0.0, domain_id="pay", headcount=20),
            Team("c", "C", True, 0.0, domain_id="pay", headcount=5),
            Team("d", "D", True, 0.0, domain_id=None, headcount=7),
        ),
        workload=1,
        domains=(
            Domain("plat", "Platform"),
            Domain("pay", "Payments", parent_id="plat"),
        ),
    )
    assert hierarchy.headcount_in_domain(org, "pay") == 25
    assert hierarchy.headcount_in_domain(org, "plat") == 35
    assert hierarchy.total_headcount(org) == 42
