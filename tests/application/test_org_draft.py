"""Tests for the editable org draft behind the editor."""

from random import Random

import pytest

from fulcrum.application.dto import (
    DependencySpec,
    DomainSpec,
    OrgBlueprint,
    TeamSpec,
)
from fulcrum.application.intake import build_org_state, org_to_blueprint
from fulcrum.application.name_pool import NamePicker
from fulcrum.application.org_draft import OrgDraft
from fulcrum.application.org_draft_nodes import (
    ContainerDraft,
    TeamDraft,
    default_category_for_depth,
)
from fulcrum.domain.models import GROUP_CATEGORIES, Origin


def _draft() -> OrgDraft:
    return OrgDraft(NamePicker(Random(0)))


def _blueprint() -> OrgBlueprint:
    return OrgBlueprint(
        teams=(
            TeamSpec(
                "team_1",
                "Checkout",
                True,
                0.25,
                domain_id="d2",
                size=2,
                owner="Priya Sharma",
                headcount=6,
            ),
            TeamSpec("team_2", "Free Agent", False, 0.4, headcount=4),
        ),
        dependencies=(DependencySpec("team_1", "team_2", 3),),
        workload=5,
        domains=(
            DomainSpec("d1", "Acme", lead="Kwame Mensah", category="Company"),
            DomainSpec(
                "d2",
                "Payments",
                parent_id="d1",
                category="Division",
                headcount=40,
            ),
        ),
    )


def test_default_category_deepens_then_saturates():
    labels = [default_category_for_depth(depth) for depth in range(7)]
    assert labels[: len(GROUP_CATEGORIES)] == list(GROUP_CATEGORIES)
    assert labels[-1] == GROUP_CATEGORIES[-1]


def test_add_container_names_categorises_and_leads():
    draft = _draft()
    root = draft.add_container(None)
    child = draft.add_container(root.id)
    grandchild = draft.add_container(child.id)
    assert root.category == "Company"
    assert root.name == "Company 1"
    assert root.lead
    assert child.category == "Group"
    assert child in root.children
    assert grandchild.category == "Division"
    assert grandchild in child.children


def test_add_team_lands_under_its_parent_with_an_owner():
    draft = _draft()
    root = draft.add_container(None)
    team = draft.add_team(root.id)
    assert team in root.children
    assert team.name == "Team 1"
    assert team.owner
    loose = draft.add_team(None)
    assert loose in draft.roots


def test_add_under_a_team_or_unknown_parent_raises():
    draft = _draft()
    root = draft.add_container(None)
    team = draft.add_team(root.id)
    with pytest.raises(KeyError):
        draft.add_team(team.id)
    with pytest.raises(KeyError):
        draft.add_container("missing")


def test_remove_prunes_subtree_and_dependencies():
    draft = OrgDraft.from_blueprint(_blueprint(), NamePicker(Random(0)))
    draft.remove("d2")
    assert draft.find("team_1") is None
    assert draft.dependencies == ()
    assert draft.find("team_2") is not None


def test_remove_unknown_raises():
    with pytest.raises(KeyError):
        _draft().remove("missing")


def test_removal_summary_counts_teams_and_people():
    draft = OrgDraft.from_blueprint(_blueprint(), NamePicker(Random(0)))
    summary = draft.removal_summary("d1")
    assert summary.name == "Acme"
    assert summary.is_container
    assert summary.team_count == 1
    assert summary.people == 6
    team_summary = draft.removal_summary("team_2")
    assert not team_summary.is_container
    assert team_summary.people == 4


def test_move_up_and_down_swap_siblings_and_stop_at_the_edges():
    draft = _draft()
    first = draft.add_container(None)
    second = draft.add_container(None)
    assert not draft.move_up(first.id)
    assert not draft.move_down(second.id)
    assert draft.move_down(first.id)
    assert draft.roots == [second, first]
    assert draft.move_up(first.id)
    assert draft.roots == [first, second]


def test_move_to_reparents_and_refuses_illegal_targets():
    draft = _draft()
    outer = draft.add_container(None)
    inner = draft.add_container(outer.id)
    team = draft.add_team(outer.id)
    assert not draft.move_to(outer.id, outer.id)
    assert not draft.move_to(outer.id, inner.id)
    assert not draft.move_to(inner.id, team.id)
    assert draft.move_to(team.id, inner.id)
    assert team in inner.children
    assert draft.move_to(inner.id, None)
    assert inner in draft.roots


def test_duplicate_copies_a_subtree_with_fresh_ids():
    draft = _draft()
    root = draft.add_container(None)
    team = draft.add_team(root.id)
    copy = draft.duplicate(root.id)
    assert copy.name == f"{root.name} copy"
    assert copy.id != root.id
    assert len(copy.children) == 1
    assert copy.children[0].id != team.id
    assert copy.children[0].name == team.name
    team_copy = draft.duplicate(team.id)
    assert team_copy.name == f"{team.name} copy"
    assert root.children == [team, team_copy]


def test_reroll_name_changes_the_name():
    draft = _draft()
    assert draft.reroll_name("Somebody Else")


def test_find_rollup_totals_and_teams():
    draft = OrgDraft.from_blueprint(_blueprint(), NamePicker(Random(0)))
    assert draft.find("missing") is None
    assert draft.rollup("d1") == (1, 6)
    assert draft.totals() == (2, 10)
    assert draft.teams() == (("team_1", "Checkout"), ("team_2", "Free Agent"))


def test_container_paths_and_move_targets():
    draft = OrgDraft.from_blueprint(_blueprint(), NamePicker(Random(0)))
    assert draft.container_paths() == (
        ("d1", "Acme"),
        ("d2", "Acme / Payments"),
    )
    assert draft.move_targets("d1") == ()
    assert draft.move_targets("team_2") == (
        ("d1", "Acme"),
        ("d2", "Acme / Payments"),
    )


def test_warnings_flag_containers_without_teams():
    draft = _draft()
    lonely = draft.add_container(None)
    parent = draft.add_container(None)
    draft.add_team(parent.id)
    warnings = draft.warnings()
    assert [w.node_id for w in warnings] == [lonely.id]
    assert lonely.name in warnings[0].message


def test_blocking_reason_requires_a_team_with_people():
    draft = _draft()
    assert "at least one team" in draft.blocking_reason().lower()
    team = draft.add_team(None)
    assert draft.blocking_reason() is None
    team.people = 0
    assert "people" in draft.blocking_reason()


def test_from_blueprint_rebuilds_the_tree_and_fills_blank_names():
    draft = OrgDraft.from_blueprint(_blueprint(), NamePicker(Random(0)))
    acme = draft.find("d1")
    payments = draft.find("d2")
    assert isinstance(acme, ContainerDraft)
    assert payments in acme.children
    assert payments.unit_headcount == 40
    assert acme.lead == "Kwame Mensah"
    assert payments.lead
    checkout = draft.find("team_1")
    assert isinstance(checkout, TeamDraft)
    assert checkout in payments.children
    assert checkout.skew_percent == 25
    assert checkout.size == 2
    free_agent = draft.find("team_2")
    assert free_agent in draft.roots
    assert free_agent.owner


def test_from_blueprint_orphans_fall_to_the_top_level():
    blueprint = OrgBlueprint(
        teams=(TeamSpec("t", "T", True, domain_id="missing"),),
        domains=(DomainSpec("d", "D", parent_id="missing"),),
    )
    draft = OrgDraft.from_blueprint(blueprint, NamePicker(Random(0)))
    assert draft.find("t") in draft.roots
    assert draft.find("d") in draft.roots


def test_to_blueprint_round_trips_losslessly():
    picker = NamePicker(Random(0))
    original = _blueprint()
    draft = OrgDraft.from_blueprint(original, picker)
    rebuilt = draft.to_blueprint()
    assert rebuilt.workload == original.workload
    assert rebuilt.dependencies == original.dependencies
    assert {t.id for t in rebuilt.teams} == {t.id for t in original.teams}
    again = OrgDraft.from_blueprint(rebuilt, picker).to_blueprint()
    assert again == rebuilt


def test_org_round_trips_through_the_draft_unchanged():
    org = build_org_state(_blueprint(), Origin.IMPORTED)
    blueprint = org_to_blueprint(org)
    draft = OrgDraft.from_blueprint(blueprint, NamePicker(Random(0)))
    rebuilt = build_org_state(draft.to_blueprint(), org.origin)
    assert rebuilt.workload == org.workload
    assert rebuilt.dependencies == org.dependencies
    assert rebuilt.domains[0].headcount == org.domains[0].headcount
    assert {t.id for t in rebuilt.teams} == {t.id for t in org.teams}
    assert rebuilt.team("team_1").incentive_skew == org.team("team_1").incentive_skew


def test_to_blueprint_falls_back_to_ids_for_blank_names():
    draft = _draft()
    container = draft.add_container(None)
    team = draft.add_team(container.id)
    container.name = ""
    team.name = ""
    blueprint = draft.to_blueprint()
    assert blueprint.domains[0].name == container.id
    assert blueprint.teams[0].name == team.id


def test_new_ids_never_collide_with_imported_ones():
    draft = OrgDraft.from_blueprint(_blueprint(), NamePicker(Random(0)))
    added = draft.add_team(None)
    assert added.id not in {"team_1", "team_2"}
    assert draft.find(added.id) is added
