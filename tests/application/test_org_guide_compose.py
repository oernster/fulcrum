"""Tests for the guarded leaf-line composition.

The two regimes the guard must tell apart: a negative applied-alone badge
whose line still helps the composed position (kept) and a line that costs
the whole organisation even after the sibling lines land (dropped).
"""

import pytest

from fulcrum.application.org_guide import build_org_guide, compose_leaf_lines
from fulcrum.application.org_guide_compose import replay_line
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.simulation import SimulationParameters

# Composition mechanics are pinned at flat authority pricing: attenuation 1
# with amplification 0 makes the prince factor 1 at every scale, so these
# carefully balanced dilution scenarios hold at any fixture headcount. The
# scale rule itself is covered by the prince-band conformance suite.
_FLAT_PRINCE = SimulationParameters(prince_attenuation=1.0, prince_amplification=0.0)
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


def _repairable_org():
    """The sibling's one problem is fixed by its own leaf line."""
    return OrgState(
        teams=_platform_teams() + (_t("app", False, 0.0, "product"),),
        dependencies=_hub_edges(),
        workload=9,
        domains=(Domain("platform", "Platform"), Domain("product", "Product")),
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


def test_negative_badge_line_composes_when_it_helps_the_composed_position():
    guide = build_org_guide(_repairable_org(), _SIM)
    platform = _leaf(guide, "Platform")
    # Applied alone the collapse dilutes the sibling's escalation share, so
    # the badge is honestly negative; after the sibling repairs itself the
    # same line is pure gain and dropping it would cost the headline.
    assert platform.org_delta < 0
    assert platform.composes is True
    assert platform.compose_cost == 0.0
    assert all(node.composes for node in guide.leaf_nodes())
    assert guide.flat_after > guide.flat_before


def test_net_harmful_line_is_dropped_from_the_headline():
    org = _residual_org()
    guide = build_org_guide(org, _SIM)
    platform = _leaf(guide, "Platform")
    assert platform.org_delta < 0
    assert platform.composes is False
    assert platform.compose_cost > 0
    # The badge still tells the applied-alone truth on the dropped row.
    assert platform.guide.steps
    product = _leaf(guide, "Product")
    assert product.composes is True


def test_dropping_the_harmful_line_raises_the_headline():
    org = _residual_org()
    guide = build_org_guide(org, _SIM)
    platform = _leaf(guide, "Platform")
    with_all = org
    for node in guide.leaf_nodes():
        with_all = replay_line(with_all, node.guide)
    assert guide.flat_after == pytest.approx(
        _SIM.score(with_all).value + platform.compose_cost
    )
    assert guide.flat_after > _SIM.score(with_all).value


def test_headline_matches_the_composition_it_advertises():
    org = _residual_org()
    guide = build_org_guide(org, _SIM)
    assert guide.flat_after == pytest.approx(
        _SIM.score(compose_leaf_lines(org, guide)).value
    )


def test_a_dropped_line_nested_under_an_aggregate_is_marked_in_place():
    org = _residual_org(platform_parent="eng")
    guide = build_org_guide(org, _SIM)
    engineering = next(n for n in guide.nodes if n.label == "Engineering")
    assert engineering.is_leaf is False
    platform = next(c for c in engineering.children if c.label == "Platform")
    assert platform.composes is False
    assert platform.compose_cost > 0
