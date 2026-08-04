"""Tests for the guarded leaf-line composition.

The two regimes the guard must tell apart: a negative applied-alone badge
whose line still helps the composed position (kept) and a line that costs
the whole organisation even after the sibling lines land (dropped).
"""

import pytest

from fulcrum.application.org_guide import (
    GuideNode,
    build_org_guide,
    compose_leaf_lines,
)
from fulcrum.application.org_guide_compose import guard_leaf_lines, replay_line
from fulcrum.application.planner import Guide, GuideStep
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind
from fulcrum.domain.simulation import MoveClassification, SimulationParameters

# Composition mechanics are pinned at flat authority pricing: attenuation 1
# with amplification 0 makes the prince factor 1 at every scale, so these
# carefully balanced dilution scenarios hold at any fixture headcount. The
# scale rule itself is covered by the prince-band conformance suite.
# Composition semantics are under test here, not pricing: flatten the
# prince band and switch off routed dependent demand so the hand-built
# fixtures keep the dilution dynamics the guard logic is probed with.
_FLAT_PRINCE = SimulationParameters(
    prince_attenuation=1.0,
    prince_amplification=0.0,
    dependent_demand_weight=0.0,
)
_SIM = DeterministicSimulator(params=_FLAT_PRINCE)

# One more troubled team than the planner's max_steps can repair, so the
# sibling frame keeps residual problems for a collapse to dilute against.
_RESIDUAL_TEAM_COUNT = 13


def _t(team_id, authority, skew, domain_id):
    return Team(
        id=team_id,
        name=team_id.upper(),
        has_local_authority=authority,
        incentive_skew=skew,
        domain_id=domain_id,
    )


def _platform_teams():
    """A healthy internal hub: its frame's best line is pure collapse."""
    return (
        _t("hub", True, 0.0, "platform"),
        _t("web", True, 0.0, "platform"),
        _t("api", True, 0.0, "platform"),
    )


def _hub_edges():
    return (
        Dependency("hub", "web", 0),
        Dependency("hub", "api", 0),
    )


def _residual_org(platform_parent=None):
    """The sibling keeps unrepaired problems beyond the planner's horizon."""
    product = tuple(
        _t(f"p{i}", False, 1.0, "product") for i in range(_RESIDUAL_TEAM_COUNT)
    )
    domains = (Domain("platform", "Platform"), Domain("product", "Product"))
    if platform_parent is not None:
        domains = (
            Domain(platform_parent, "Engineering"),
            Domain("platform", "Platform", parent_id=platform_parent),
            Domain("product", "Product"),
        )
    return OrgState(
        teams=_platform_teams() + product,
        dependencies=_hub_edges(),
        workload=9,
        domains=domains,
    )


def _leaf(guide, label):
    return next(n for n in guide.leaf_nodes() if n.label == label)


# The guard scenarios are driven with hand-built lines so the dilution
# wedge is explicit: an officer-roofed sovereign pair whose collapse costs
# only the sibling's per-team shares (escalation and rework dilution),
# beside a sibling frame whose own line may or may not repair it. Under
# honest frame pricing the planner rarely authors such a line unaided,
# but imported plans and future planners can, and the guard is the last
# line of defence either way.
def _guard_org():
    return OrgState(
        teams=(
            _t("a", True, 0.0, "platform"),
            _t("b", True, 0.0, "platform"),
            _t("c", True, 0.0, "platform"),
            _t("s", False, 0.5, "product"),
        ),
        dependencies=(Dependency("a", "b", 1),),
        workload=7,
        domains=(Domain("platform", "Platform"), Domain("product", "Product")),
    )


def _line(org, *moves):
    steps = tuple(
        GuideStep(move, MoveClassification.NEUTRAL, 0.0, org, 0.0) for move in moves
    )
    return Guide(0.0, 0.0, steps)


def _node(label, frame_id, line, children=(), leaf=True):
    return GuideNode(
        frame_id=frame_id,
        label=label,
        category="",
        is_leaf=leaf,
        playable=True,
        guide=line,
        children=children,
    )


def _collapse_node(org):
    return _node(
        "Platform", "platform", _line(org, Move(MoveKind.COLLAPSE_BOUNDARY, ("a", "b")))
    )


def test_negative_badge_line_composes_when_it_helps_the_composed_position():
    # Applied alone the collapse only dilutes the sibling's per-team
    # shares, so the badge is honestly negative; after the sibling's line
    # fully repairs its own frame the same collapse costs nothing and
    # dropping it would be wrong.
    org = _guard_org()
    platform = _collapse_node(org)
    product = _node(
        "Product",
        "product",
        _line(
            org,
            Move(MoveKind.DELEGATE_AUTHORITY, ("s",)),
            Move(MoveKind.REALIGN_INCENTIVES, ("s",)),
        ),
    )
    alone = _SIM.score(replay_line(org, platform.guide)).value
    assert alone < _SIM.score(org).value
    nodes, composed = guard_leaf_lines(org, _SIM, (platform, product))
    assert all(node.composes for node in nodes)
    assert all(node.compose_cost == 0.0 for node in nodes)
    assert _SIM.score(composed).value > _SIM.score(org).value


def _harmful_nodes(org):
    """The collapse beside a sibling line that leaves its frame broken."""
    platform = _collapse_node(org)
    product = _node(
        "Product", "product", _line(org, Move(MoveKind.REALIGN_INCENTIVES, ("s",)))
    )
    return platform, product


def test_net_harmful_line_is_dropped_from_the_headline():
    org = _guard_org()
    platform, product = _harmful_nodes(org)
    nodes, _composed = guard_leaf_lines(org, _SIM, (platform, product))
    marked = next(n for n in nodes if n.label == "Platform")
    assert marked.composes is False
    assert marked.compose_cost > 0
    # The dropped row keeps its line: the badge still tells the truth.
    assert marked.guide.steps
    assert next(n for n in nodes if n.label == "Product").composes is True


def test_dropping_the_harmful_line_raises_the_headline():
    org = _guard_org()
    platform, product = _harmful_nodes(org)
    nodes, composed = guard_leaf_lines(org, _SIM, (platform, product))
    marked = next(n for n in nodes if n.label == "Platform")
    with_all = replay_line(replay_line(org, platform.guide), product.guide)
    headline = _SIM.score(composed).value
    assert headline == pytest.approx(_SIM.score(with_all).value + marked.compose_cost)
    assert headline > _SIM.score(with_all).value


def test_headline_matches_the_composition_it_advertises():
    org = _residual_org()
    guide = build_org_guide(org, _SIM)
    assert guide.flat_after == pytest.approx(
        _SIM.score(compose_leaf_lines(org, guide)).value
    )


def test_a_dropped_line_nested_under_an_aggregate_is_marked_in_place():
    org = _guard_org()
    platform, product = _harmful_nodes(org)
    engineering = _node("Engineering", "eng", Guide(0.0, 0.0, ()), (platform,), False)
    nodes, _ = guard_leaf_lines(org, _SIM, (engineering, product))
    marked_parent = next(n for n in nodes if n.label == "Engineering")
    assert marked_parent.is_leaf is False
    marked = next(c for c in marked_parent.children if c.label == "Platform")
    assert marked.composes is False
    assert marked.compose_cost > 0
