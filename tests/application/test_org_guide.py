"""Tests for the whole-hierarchy guide builder."""

from fulcrum.application.game_session import MAX_PLAYABLE_TEAMS
from fulcrum.application.org_guide import (
    TOP_FRAME_LABEL,
    WHOLE_ORG_LABEL,
    GuideNode,
    OrgGuide,
    build_org_guide,
    compose_leaf_lines,
)
from fulcrum.application.planner import Guide, GuideStep
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.hierarchy import AGGREGATE_MOVE_KINDS
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
    assert guide.nodes[0].label == TOP_FRAME_LABEL
    assert guide.nodes[0].is_leaf is False
    labels = {node.label for node in guide.nodes}
    assert labels == {TOP_FRAME_LABEL, "Platform", "Product"}
    product = next(n for n in guide.nodes if n.label == "Product")
    assert product.is_leaf is False
    assert {c.label for c in product.children} == {"Web", "Mobile"}
    assert all(child.is_leaf for child in product.children)


def test_aggregate_rows_only_offer_translatable_kinds():
    guide = build_org_guide(_hierarchical_org(), _SIM)
    for node in (guide.nodes[0], guide.nodes[2]):
        kinds = {step.move.kind for step in node.guide.steps}
        assert kinds <= set(AGGREGATE_MOVE_KINDS)


def test_leaf_lines_compose_to_a_stronger_flat_score():
    guide = build_org_guide(_hierarchical_org(), _SIM)
    assert guide.flat_before == _SIM.score(_hierarchical_org()).value
    assert guide.flat_after > guide.flat_before


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


def test_progress_reports_every_planned_section():
    seen = []
    build_org_guide(
        _hierarchical_org(),
        _SIM,
        progress=lambda done, total: seen.append((done, total)),
    )
    # Top frame, Platform, Product, Web, Mobile: five sections.
    assert seen == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]


def test_growth_flag_is_carried_on_the_result():
    fixed = build_org_guide(_hierarchical_org(), _SIM)
    grown = build_org_guide(_hierarchical_org(), _SIM, allow_growth=True)
    assert fixed.grown is False
    assert grown.grown is True


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
