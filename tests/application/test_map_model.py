"""Tests for the org-map drill-level view model."""

from fulcrum.application.map_model import build_level
from fulcrum.domain.models import Dependency, Domain, OrgState, Team


def _hierarchical():
    return OrgState(
        teams=(
            Team("a", "A", True, 0.0, domain_id="plat"),
            Team("b", "B", False, 0.0, domain_id="pay", owner="Bo"),
            Team("c", "C", True, 0.0, domain_id="pay"),
            Team("u", "U", True, 0.0, domain_id=None),
        ),
        dependencies=(
            Dependency("a", "b", 1),
            Dependency("a", "c", 1),
            Dependency("b", "c", 1),
            Dependency("u", "a", 1),
        ),
        workload=3,
        domains=(
            Domain("plat", "Platform"),
            Domain("pay", "Payments", lead="Dana"),
            Domain("empty", "Empty"),
        ),
    )


def test_top_level_aggregates_domains_and_unassigned_teams():
    nodes, edges = build_level(_hierarchical())
    by_id = {n.id: n for n in nodes}
    assert by_id["plat"].kind == "domain" and by_id["plat"].team_count == 1
    assert by_id["pay"].team_count == 2 and by_id["pay"].authority_ratio == 0.5
    assert by_id["empty"].team_count == 0 and by_id["empty"].authority_ratio == 0.0
    assert by_id["u"].kind == "team" and by_id["u"].authority_ratio == 1.0
    assert by_id["pay"].owner == "Dana"
    assert by_id["u"].owner == ""
    weights = {(e.source, e.target): e.weight for e in edges}
    assert weights == {("plat", "pay"): 2, ("u", "plat"): 1}


def test_drilling_into_a_domain_shows_its_teams_and_internal_edges():
    nodes, edges = build_level(_hierarchical(), "pay")
    assert {n.id for n in nodes} == {"b", "c"}
    assert all(n.kind == "team" for n in nodes)
    assert {n.id: n.owner for n in nodes}["b"] == "Bo"
    assert {(e.source, e.target): e.weight for e in edges} == {("b", "c"): 1}


def test_flat_org_without_domains_shows_every_team():
    org = OrgState(
        teams=(Team("x", "X", True, 0.0), Team("y", "Y", False, 0.0)),
        dependencies=(Dependency("x", "y", 2),),
        workload=2,
    )
    nodes, edges = build_level(org)
    assert {n.id for n in nodes} == {"x", "y"}
    assert all(n.kind == "team" for n in nodes)
    assert {(e.source, e.target): e.weight for e in edges} == {("x", "y"): 1}


def test_headcount_sums_on_domain_nodes_and_shows_on_team_nodes():
    org = OrgState(
        teams=(
            Team("a", "A", True, 0.0, domain_id="plat", headcount=10),
            Team("b", "B", False, 0.0, domain_id="pay", headcount=20),
            Team("c", "C", True, 0.0, domain_id="pay", headcount=5),
            Team("u", "U", True, 0.0, domain_id=None, headcount=7),
        ),
        workload=1,
        domains=(Domain("plat", "Platform"), Domain("pay", "Payments")),
    )
    nodes = {n.id: n for n in build_level(org)[0]}
    assert nodes["plat"].headcount == 10
    assert nodes["pay"].headcount == 25
    assert nodes["u"].headcount == 7


def test_unit_level_dependencies_draw_between_matching_nodes():
    org = OrgState(
        teams=(
            Team("a", "A", True, 0.0, domain_id="plat"),
            Team("b", "B", True, 0.0, domain_id="pay"),
        ),
        dependencies=(Dependency("plat", "pay", 4),),
        workload=1,
        domains=(Domain("plat", "Platform"), Domain("pay", "Payments")),
    )
    _, edges = build_level(org, None)
    assert [(e.source, e.target, e.weight) for e in edges] == [("plat", "pay", 1)]
