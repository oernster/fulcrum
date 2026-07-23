"""Tests for the editable org draft's structure operations and queries.

Serialisation lives in test_org_draft_io, conversions in
test_org_draft_convert; the shared builders in org_draft_support.
"""

import pytest

from org_draft_support import make_draft, make_imported_draft

from fulcrum.application.dto import DependencySpec
from fulcrum.application.org_draft_nodes import (
    GREEK_SEQUENCE,
    can_nest,
    default_category_for_depth,
    retitle_for_category,
    sequence_token,
)
from fulcrum.domain.models import GROUP_CATEGORIES


def test_default_category_deepens_then_saturates():
    labels = [default_category_for_depth(depth) for depth in range(7)]
    assert labels[: len(GROUP_CATEGORIES)] == list(GROUP_CATEGORIES)
    assert labels[-1] == GROUP_CATEGORIES[-1]


def test_sequence_tokens_run_greek_then_wrap_with_a_lap_number():
    assert sequence_token(1) == "Alpha"
    assert sequence_token(2) == "Beta"
    assert sequence_token(len(GREEK_SEQUENCE)) == "Omega"
    assert sequence_token(len(GREEK_SEQUENCE) + 1) == "Alpha 2"


def test_add_container_names_categorises_and_leads():
    draft = make_draft()
    root = draft.add_container(None)
    child = draft.add_container(root.id)
    grandchild = draft.add_container(child.id)
    assert root.category == "Company"
    assert root.name == "Company Alpha"
    assert root.lead
    assert child.category == "Group"
    assert child.name == "Group Beta"
    assert child in root.children
    assert grandchild.category == "Division"
    assert grandchild in child.children


def test_add_container_with_an_explicit_category_overrides_the_depth():
    draft = make_draft()
    division = draft.add_container(None, "Division")
    assert division.category == "Division"
    assert division.name == "Division Alpha"
    nested = draft.add_container(division.id, "Domain")
    assert nested.category == "Domain"
    assert nested.name == "Domain Beta"
    assert nested in division.children


def test_add_team_lands_under_its_parent_with_an_owner():
    draft = make_draft()
    root = draft.add_container(None)
    team = draft.add_team(root.id)
    assert team in root.children
    assert team.name == "Team Alpha"
    assert team.owner
    loose = draft.add_team(None)
    assert loose.name == "Team Beta"
    assert loose in draft.roots


def test_add_under_a_team_or_unknown_parent_raises():
    draft = make_draft()
    root = draft.add_container(None)
    team = draft.add_team(root.id)
    with pytest.raises(KeyError):
        draft.add_team(team.id)
    with pytest.raises(KeyError):
        draft.add_container("missing")


def test_remove_prunes_subtree_and_dependencies():
    draft = make_imported_draft()
    draft.remove("d2")
    assert draft.find("team_1") is None
    assert draft.dependencies == ()
    assert draft.find("team_2") is not None


def test_remove_unknown_raises():
    with pytest.raises(KeyError):
        make_draft().remove("missing")


def test_removal_summary_counts_teams_and_people():
    draft = make_imported_draft()
    summary = draft.removal_summary("d1")
    assert summary.name == "Acme"
    assert summary.is_container
    assert summary.team_count == 1
    assert summary.people == 6
    team_summary = draft.removal_summary("team_2")
    assert not team_summary.is_container
    assert team_summary.people == 4


def test_move_up_and_down_swap_siblings_and_stop_at_the_edges():
    draft = make_draft()
    first = draft.add_container(None)
    second = draft.add_container(None)
    assert not draft.move_up(first.id)
    assert not draft.move_down(second.id)
    assert draft.move_down(first.id)
    assert draft.roots == [second, first]
    assert draft.move_up(first.id)
    assert draft.roots == [first, second]


def test_move_to_reparents_and_refuses_illegal_targets():
    draft = make_draft()
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
    draft = make_draft()
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
    draft = make_draft()
    assert draft.reroll_name("Somebody Else")


def test_find_rollup_totals_and_teams():
    draft = make_imported_draft()
    assert draft.find("missing") is None
    assert draft.rollup("d1") == (1, 6)
    assert draft.totals() == (2, 10)
    assert draft.teams() == (("team_1", "Checkout"), ("team_2", "Free Agent"))


def test_container_paths_and_move_targets():
    draft = make_imported_draft()
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
    draft = make_draft()
    lonely = draft.add_container(None)
    parent = draft.add_container(None)
    draft.add_team(parent.id)
    warnings = draft.warnings()
    assert [w.node_id for w in warnings] == [lonely.id]
    assert lonely.name in warnings[0].message


def test_blocking_reason_requires_a_team_with_people():
    draft = make_draft()
    assert "at least one team" in draft.blocking_reason().lower()
    team = draft.add_team(None)
    assert draft.blocking_reason() is None
    team.people = 0
    assert "people" in draft.blocking_reason()


def test_new_ids_never_collide_with_imported_ones():
    draft = make_imported_draft()
    added = draft.add_team(None)
    assert added.id not in {"team_1", "team_2"}
    assert draft.find(added.id) is added


def test_can_nest_enforces_tier_order_only_for_known_tiers():
    assert can_nest("Division", "Company")
    assert can_nest("Domain", "Company")
    assert can_nest("Domain", "Domain")
    assert not can_nest("Company", "Division")
    assert can_nest("Tribe", "Division")
    assert can_nest("Company", "Tribe")


def test_retitle_follows_only_auto_generated_names():
    assert retitle_for_category("Company Alpha", "Company", "Group") == "Group Alpha"
    assert retitle_for_category("Company Alpha 2", "Company", "Group") == (
        "Group Alpha 2"
    )
    assert retitle_for_category("Company 1", "Company", "Group") == "Group 1"
    assert retitle_for_category("Acme", "Company", "Group") == "Acme"
    assert retitle_for_category("Company Alpha copy", "Company", "Group") == (
        "Company Alpha copy"
    )


def test_move_to_with_index_reorders_within_a_parent():
    draft = make_draft()
    parent = draft.add_container(None)
    first = draft.add_team(parent.id)
    second = draft.add_team(parent.id)
    third = draft.add_team(parent.id)
    assert draft.move_to(first.id, parent.id, 3)
    assert parent.children == [second, third, first]
    assert draft.move_to(first.id, parent.id, 0)
    assert parent.children == [first, second, third]


def test_move_to_refuses_a_tier_above_the_parent():
    draft = make_draft()
    company = draft.add_container(None)
    division = draft.add_container(None)
    division.category = "Division"
    assert not draft.move_to(company.id, division.id)
    assert draft.move_to(division.id, company.id)


def test_can_place_covers_every_refusal():
    draft = make_imported_draft()
    assert draft.can_place("team_2", "d2")
    assert draft.can_place("d2", None)
    assert not draft.can_place("d1", "d2")
    assert not draft.can_place("team_2", "team_1")
    assert not draft.can_place("d1", "d1")


def test_copy_into_copies_a_subtree_with_fresh_ids():
    draft = make_imported_draft()
    copy = draft.copy_into("d2", None, 0)
    assert copy is not None
    assert draft.roots[0] is copy
    assert copy.id != "d2"
    assert copy.name == "Payments"
    assert copy.children[0].id != "team_1"
    assert draft.copy_into("d1", "d2") is None


def test_can_depend_blocks_self_and_related_nodes_only():
    draft = make_draft()
    company = draft.add_container(None)
    division = draft.add_container(company.id)
    team = draft.add_team(division.id)
    other = draft.add_container(None)
    other_team = draft.add_team(other.id)
    assert draft.can_depend(division.id, other.id)
    assert draft.can_depend(other_team.id, division.id)
    assert draft.can_depend(team.id, other.id)
    assert not draft.can_depend(team.id, team.id)
    assert not draft.can_depend(team.id, division.id)
    assert not draft.can_depend(company.id, team.id)
    assert not draft.can_depend(team.id, "ghost")
    assert not draft.can_depend("ghost", team.id)


def test_dependency_options_list_teams_then_unit_paths():
    draft = make_draft()
    company = draft.add_container(None)
    team = draft.add_team(company.id)
    options = draft.dependency_options()
    assert options[0] == (team.id, team.name)
    assert options[-1][0] == company.id
    assert company.name in options[-1][1]


def test_removing_a_unit_prunes_dependencies_it_carried():
    draft = make_draft()
    first = draft.add_container(None)
    second = draft.add_container(None)
    second_team = draft.add_team(second.id)
    draft.dependencies = (DependencySpec(first.id, second_team.id, 2),)
    draft.remove(first.id)
    assert draft.dependencies == ()
