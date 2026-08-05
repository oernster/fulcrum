"""Tests for the standalone SVG overview renderer."""

import re

from fulcrum.domain.models import AuthorityClaim, Dependency, Domain, OrgState, Team
from fulcrum.infrastructure.svg_map import (
    _LABEL_PT,
    _SUB_PT,
    _TEXT_INSET,
    _node_lines,
    node_width,
    render_overview_svg,
    text_width,
)
from fulcrum.application.map_model import build_level


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


def test_overview_svg_marks_contested_nodes_in_violet():
    org = OrgState(
        teams=(
            Team("x", "X", True),
            Team("y", "Y", True, domain_id="unit"),
        ),
        workload=1,
        domains=(Domain("unit", "Unit"),),
        claims=(AuthorityClaim("y", "x"), AuthorityClaim("x", "y")),
    )
    svg = render_overview_svg(org)
    assert "contested" in svg
    assert "1 contested team" in svg
    assert "#a855f7" in svg


# ----------------------------------------------- text stays inside its box


def _crowded(team_count: int, contested: int) -> OrgState:
    """A single domain whose subtitle is far wider than the old fixed width."""
    teams = []
    claims = []
    for index in range(team_count):
        teams.append(Team(f"t{index}", f"Team {index}", True, domain_id="unit"))
    for index in range(contested):
        claims.append(AuthorityClaim(f"t{index}", f"t{(index + 1) % team_count}"))
    return OrgState(
        teams=tuple(teams),
        workload=1,
        domains=(Domain("unit", "Company"),),
        claims=tuple(claims),
    )


def _fits(org: OrgState) -> None:
    """Every line of every node must sit inside the node rectangle."""
    nodes, _ = build_level(org)
    usable = node_width(nodes) - _TEXT_INSET * 2
    for node in nodes:
        label, sub, owner = _node_lines(node)
        assert text_width(label, _LABEL_PT, bold=True) <= usable, label
        assert text_width(sub, _SUB_PT) <= usable, sub
        if owner is not None:
            assert text_width(owner, _SUB_PT) <= usable, owner


def test_a_long_subtitle_widens_the_node_instead_of_spilling_out_of_it():
    # The reported defect: a domain with enough teams for a four-figure count
    # plus a contested count produced a subtitle half as wide again as the
    # fixed 180-unit box, so it ran out past the border in the report.
    org = _crowded(1076, 177)
    nodes, _ = build_level(org)
    _, sub, _ = _node_lines(nodes[0])
    assert sub == "1,076 teams, 177 contested teams"
    assert node_width(nodes) > 180
    _fits(org)


def test_every_node_line_fits_across_awkward_labels():
    for label in (
        "M" * 30,
        "WWWWWWWWWW",
        "iiiiiiiiiiiiiiiiiiii",
        "MIXED Case With Capitals And Descenders",
        "1,234,567",
        "R&D",
        "x",
    ):
        org = OrgState(
            teams=(Team("t", "T", True, domain_id="unit"),),
            workload=1,
            domains=(Domain("unit", label),),
        )
        _fits(org)


def test_a_long_owner_name_also_widens_the_node():
    org = OrgState(
        teams=(
            Team(
                "t",
                "Team",
                True,
                owner="Wilhelmina Mountbatten-Wodehouse",
            ),
        ),
        workload=1,
    )
    _fits(org)
    assert "owner: Wilhelmina Mountbatten-Wodehouse" in render_overview_svg(org)


def test_the_rendered_rect_is_always_wide_enough_for_its_text():
    # Measured against the emitted SVG rather than the helpers, so a renderer
    # that stopped using node_width could not pass this.
    svg = render_overview_svg(_crowded(1076, 177))
    width = float(re.search(r'<rect x="\d+" y="\d+" width="(\d+)"', svg).group(1))
    for size, text in re.findall(r'font-size="(\d+)"[^>]*>([^<]+)</text>', svg):
        bold = int(size) == _LABEL_PT
        assert text_width(text, int(size), bold=bold) <= width - _TEXT_INSET * 2, text


def test_the_width_estimate_is_never_smaller_than_the_class_it_stands_for():
    # The estimate is an upper bound by construction: every character costs at
    # least the default weight, so a string can never be measured under a
    # narrower one of the same length.
    assert text_width("mmmm", 12) > text_width("iiii", 12)
    assert text_width("MMMM", 12) > text_width("aaaa", 12)
    assert text_width("Test", 12, bold=True) > text_width("Test", 12)
    assert text_width("", 12) == 0.0
