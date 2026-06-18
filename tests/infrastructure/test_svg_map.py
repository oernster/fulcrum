"""Tests for the standalone SVG overview renderer."""

from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.infrastructure.svg_map import render_overview_svg


def _hierarchical():
    return OrgState(
        teams=(
            Team("a", "Alpha", True, 0.0, domain_id="plat"),
            Team("b", "Bravo", False, 0.0, domain_id="pay"),
            Team("c", "Charlie", True, 0.0, domain_id="pay"),
            Team("u", "R&D", False, 0.0, domain_id=None, owner="Uli"),
        ),
        dependencies=(
            Dependency("a", "b", 1),
            Dependency("a", "c", 1),
            Dependency("b", "u", 1),
        ),
        workload=3,
        domains=(Domain("plat", "Platform"), Domain("pay", "Payments")),
    )


def test_overview_svg_has_nodes_edges_and_escapes_names():
    svg = render_overview_svg(_hierarchical())
    assert svg.startswith("<svg")
    assert "Platform" in svg and "Payments" in svg
    assert "teams" in svg
    assert "escalates" in svg
    assert "R&amp;D" in svg
    assert "owner: Uli" in svg
    assert ">2<" in svg


def test_overview_svg_for_a_flat_org():
    org = OrgState(
        teams=(Team("x", "X", True), Team("y", "Y", False)),
        dependencies=(Dependency("x", "y", 1),),
        workload=2,
    )
    svg = render_overview_svg(org)
    assert "decides locally" in svg and "escalates" in svg
