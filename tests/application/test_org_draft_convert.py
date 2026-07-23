"""Tests for the draft's type conversions (org_draft_convert)."""

from org_draft_support import make_draft, make_imported_draft

from fulcrum.application.org_draft_nodes import ContainerDraft, TeamDraft


def test_set_category_retitles_and_guards_the_tier():
    draft = make_draft()
    company = draft.add_container(None)
    child = draft.add_container(company.id)
    assert draft.set_category(company.id, "Group")
    assert company.name == "Group Alpha"
    assert not draft.set_category(child.id, "Company")
    assert draft.set_category(child.id, "Domain")
    team = draft.add_team(company.id)
    assert not draft.set_category(team.id, "Division")


def test_convert_team_to_container_and_back():
    draft = make_imported_draft()
    owner = draft.find("team_2").owner
    unit = draft.convert_to_container("team_2", "Division")
    assert isinstance(unit, ContainerDraft)
    assert unit.id == "team_2"
    assert unit.lead == owner
    assert draft.dependencies == ()
    team = draft.convert_to_team("team_2")
    assert isinstance(team, TeamDraft)
    assert team.owner == owner


def test_convert_refusals():
    draft = make_imported_draft()
    assert draft.convert_to_team("d1") is None
    assert draft.convert_to_team("team_2") is None
    assert draft.convert_to_container("d1", "Division") is None
    division = draft.find("d2")
    division.children.clear()
    assert draft.convert_to_team("d2") is not None


def test_convert_respects_the_parent_tier():
    draft = make_draft()
    division = draft.add_container(None)
    division.category = "Division"
    team = draft.add_team(division.id)
    assert draft.convert_to_container(team.id, "Company") is None
    assert draft.convert_to_container(team.id, "Domain") is not None


def test_conversion_retitles_auto_names():
    draft = make_draft()
    parent = draft.add_container(None)
    team = draft.add_team(parent.id)
    unit = draft.convert_to_container(team.id, "Division")
    assert unit.name == "Division Alpha"
    back = draft.convert_to_team(unit.id)
    assert back.name == "Team Alpha"


def test_parent_of_finds_the_holder():
    draft = make_imported_draft()
    assert draft.parent_of("team_1").id == "d2"
    assert draft.parent_of("d2").id == "d1"
    assert draft.parent_of("d1") is None
    assert draft.parent_of("team_2") is None
