"""Tests for the draft's blueprint serialisation (org_draft_io)."""

from random import Random

from org_draft_support import make_blueprint, make_draft, make_imported_draft

from fulcrum.application.dto import (
    DependencySpec,
    DomainSpec,
    OrgBlueprint,
    TeamSpec,
)
from fulcrum.application.intake import build_org_state, org_to_blueprint
from fulcrum.application.name_pool import NamePicker
from fulcrum.application.org_draft import OrgDraft
from fulcrum.application.org_draft_nodes import ContainerDraft, TeamDraft
from fulcrum.domain.models import Origin


def test_from_blueprint_rebuilds_the_tree_and_fills_blank_names():
    draft = make_imported_draft()
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
    original = make_blueprint()
    draft = OrgDraft.from_blueprint(original, picker)
    rebuilt = draft.to_blueprint()
    assert rebuilt.workload == original.workload
    assert rebuilt.dependencies == original.dependencies
    assert {t.id for t in rebuilt.teams} == {t.id for t in original.teams}
    again = OrgDraft.from_blueprint(rebuilt, picker).to_blueprint()
    assert again == rebuilt


def test_org_round_trips_through_the_draft_unchanged():
    org = build_org_state(make_blueprint(), Origin.IMPORTED)
    blueprint = org_to_blueprint(org)
    draft = OrgDraft.from_blueprint(blueprint, NamePicker(Random(0)))
    rebuilt = build_org_state(draft.to_blueprint(), org.origin)
    assert rebuilt.workload == org.workload
    assert rebuilt.dependencies == org.dependencies
    assert rebuilt.domains[0].headcount == org.domains[0].headcount
    assert {t.id for t in rebuilt.teams} == {t.id for t in org.teams}
    assert rebuilt.team("team_1").incentive_skew == org.team("team_1").incentive_skew


def test_to_blueprint_falls_back_to_ids_for_blank_names():
    draft = make_draft()
    container = draft.add_container(None)
    team = draft.add_team(container.id)
    container.name = ""
    team.name = ""
    blueprint = draft.to_blueprint()
    assert blueprint.domains[0].name == container.id
    assert blueprint.teams[0].name == team.id


def test_to_blueprint_keeps_unit_level_dependencies():
    draft = make_draft()
    unit = draft.add_container(None)
    draft.add_team(unit.id)
    other = draft.add_container(None)
    other_team = draft.add_team(other.id)
    draft.dependencies = (
        DependencySpec(unit.id, other.id, 3),
        DependencySpec("ghost", other_team.id, 1),
    )
    blueprint = draft.to_blueprint()
    assert blueprint.dependencies == (DependencySpec(unit.id, other.id, 3),)
