"""Tests for the whole-hierarchy guide builder."""

import pytest

from fulcrum.application.game_session import MAX_PLAYABLE_TEAMS
from fulcrum.application.org_guide import (
    LOOSE_TEAMS_FRAME,
    LOOSE_TEAMS_LABEL,
    WHOLE_ORG_LABEL,
    GuideNode,
    OrgGuide,
    build_org_guide,
    compose_leaf_lines,
    direct_teams_frame,
)
from fulcrum.application.planner import Guide, GuideStep
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.hierarchy import AGGREGATE_MOVE_KINDS, TOP_LEVEL_FOCUS
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind
from fulcrum.domain.simulation import MoveClassification

_SIM = DeterministicSimulator()


def _t(team_id, authority=False, skew=0.4, domain_id=None):
    return Team(
        id=team_id,
        name=team_id.upper(),
        has_local_authority=authority,
        incentive_skew=skew,
        domain_id=domain_id,
    )


def _flat_org():
    return OrgState(
        teams=(_t("a"), _t("b", authority=True, skew=0.0)),
        dependencies=(Dependency("a", "b", 4),),
        workload=2,
    )


def _hierarchical_org():
    return OrgState(
        teams=(
            _t("a1", domain_id="d1"),
            _t("a2", domain_id="d1"),
            _t("b1", domain_id="d2a"),
            _t("b2", domain_id="d2b"),
        ),
        dependencies=(
            Dependency("a1", "a2", 4),
            Dependency("d1", "d2", 6),
        ),
        workload=2,
        domains=(
            Domain("d1", "Platform"),
            Domain("d2", "Product"),
            Domain("d2a", "Web", parent_id="d2"),
            Domain("d2b", "Mobile", parent_id="d2"),
            Domain("empty", "Empty"),
        ),
    )


def test_flat_org_gets_a_single_composable_row():
    guide = build_org_guide(_flat_org(), _SIM)
    assert len(guide.nodes) == 1
    node = guide.nodes[0]
    assert node.label == WHOLE_ORG_LABEL
    assert node.is_leaf and node.playable
    assert node.guide.steps
    assert guide.flat_after > guide.flat_before


def test_hierarchy_plans_every_frame_and_skips_empty_units():
    guide = build_org_guide(_hierarchical_org(), _SIM)
    labels = {node.label for node in guide.nodes}
    assert labels == {"Platform", "Product"}
    # No top-frame row: nothing sits above the top level to make a move.
    assert all(node.frame_id != TOP_LEVEL_FOCUS for node in guide.nodes)
    product = next(n for n in guide.nodes if n.label == "Product")
    assert product.is_leaf is False
    assert {c.label for c in product.children} == {"Web", "Mobile"}
    assert all(child.is_leaf for child in product.children)


def test_aggregate_rows_only_offer_translatable_kinds():
    guide = build_org_guide(_hierarchical_org(), _SIM)
    product = next(n for n in guide.nodes if n.label == "Product")
    kinds = {step.move.kind for step in product.guide.steps}
    assert kinds <= set(AGGREGATE_MOVE_KINDS)


def test_leaf_lines_compose_to_a_stronger_flat_score():
    guide = build_org_guide(_hierarchical_org(), _SIM)
    assert guide.flat_before == _SIM.score(_hierarchical_org()).value
    assert guide.flat_after > guide.flat_before


def test_leaf_rows_carry_their_worth_in_org_points():
    guide = build_org_guide(_hierarchical_org(), _SIM)
    leaves = guide.leaf_nodes()
    assert leaves
    # Every leaf line with steps is worth real whole-org points; aggregate
    # rows advertise none, since they are views rather than repairs.
    for leaf in leaves:
        if leaf.guide.steps:
            assert leaf.org_delta > 0
    for node in guide.nodes:
        if not node.is_leaf:
            assert node.org_delta == 0.0


def test_a_flat_org_delta_matches_its_own_line():
    guide = build_org_guide(_flat_org(), _SIM)
    node = guide.nodes[0]
    assert node.org_delta == pytest.approx(guide.flat_after - guide.flat_before)


def test_a_unit_whose_children_hold_no_teams_plays_as_a_leaf():
    org = OrgState(
        teams=(_t("a", domain_id="d1"),),
        workload=1,
        domains=(Domain("d1", "One"), Domain("d1x", "Bare", parent_id="d1")),
    )
    guide = build_org_guide(org, _SIM)
    unit = next(n for n in guide.nodes if n.label == "One")
    assert unit.is_leaf is True
    assert unit.children == ()


def test_an_oversized_section_is_reported_unplannable():
    teams = tuple(_t(f"t{i}", domain_id="big") for i in range(MAX_PLAYABLE_TEAMS + 1))
    org = OrgState(teams=teams, workload=1, domains=(Domain("big", "Big"),))
    guide = build_org_guide(org, _SIM)
    unit = next(n for n in guide.nodes if n.label == "Big")
    assert unit.playable is False
    assert unit.guide.steps == ()


def _mixed_org():
    """A mixed unit (a direct team beside a teamful child unit) plus a loose team."""
    return OrgState(
        teams=(
            _t("direct", domain_id="mix"),
            _t("s1", domain_id="sub"),
            _t("s2", authority=True, skew=0.0, domain_id="sub"),
            _t("loose"),
        ),
        dependencies=(Dependency("s1", "s2", 4),),
        workload=2,
        domains=(Domain("mix", "Mixed"), Domain("sub", "Sub", parent_id="mix")),
    )


def test_a_mixed_unit_gets_a_composable_direct_teams_row():
    guide = build_org_guide(_mixed_org(), _SIM)
    mixed = next(n for n in guide.nodes if n.label == "Mixed")
    assert mixed.is_leaf is False
    direct = mixed.children[0]
    assert direct.label == "Teams directly in Mixed"
    assert direct.frame_id == direct_teams_frame("mix")
    assert direct.is_leaf and direct.playable
    assert direct.org_delta > 0
    targets = {t for s in direct.guide.steps for t in s.move.targets}
    assert "direct" in targets
    assert direct in guide.leaf_nodes()


def test_loose_top_level_teams_get_a_composable_row():
    guide = build_org_guide(_mixed_org(), _SIM)
    loose = guide.nodes[0]
    assert loose.label == LOOSE_TEAMS_LABEL
    assert loose.frame_id == LOOSE_TEAMS_FRAME
    assert loose.is_leaf and loose.org_delta > 0
    targets = {t for s in loose.guide.steps for t in s.move.targets}
    assert targets == {"loose"}


def test_direct_and_loose_repairs_reach_the_composed_headline():
    org = _mixed_org()
    guide = build_org_guide(org, _SIM)
    composed = compose_leaf_lines(org, guide)
    assert composed.team("direct").has_local_authority is True
    assert composed.team("loose").has_local_authority is True


def test_compose_stops_a_line_that_cannot_replay_and_keeps_the_rest():
    org = _flat_org()
    bad_then_good = Guide(
        0.0,
        0.0,
        (
            GuideStep(
                Move(MoveKind.DELEGATE_AUTHORITY, ("ghost",)),
                MoveClassification.GOOD,
                0.0,
                org,
                0.0,
            ),
        ),
    )
    good = Guide(
        0.0,
        0.0,
        (
            GuideStep(
                Move(MoveKind.DELEGATE_AUTHORITY, ("a",)),
                MoveClassification.GOOD,
                0.0,
                org,
                0.0,
            ),
        ),
    )
    tree = OrgGuide(
        nodes=(
            GuideNode(None, "x", "", True, True, bad_then_good),
            GuideNode(None, "y", "", True, True, good),
        ),
        flat_before=0.0,
        flat_after=0.0,
        grown=False,
    )
    composed = compose_leaf_lines(org, tree)
    assert composed.team("a").has_local_authority is True
