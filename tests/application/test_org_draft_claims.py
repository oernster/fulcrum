"""Tests for the org draft's authority-claim operations and round-tripping."""

from random import Random

from org_draft_support import make_blueprint, make_draft, make_imported_draft

from fulcrum.application.dto import ClaimSpec, OrgBlueprint
from fulcrum.application.name_pool import NamePicker
from fulcrum.application.org_draft import OrgDraft


def _draft_with_two_teams():
    draft = make_draft()
    unit = draft.add_container(None)
    first = draft.add_team(unit.id)
    second = draft.add_team(unit.id)
    return draft, unit, first, second


def test_can_claim_rules():
    draft, unit, first, second = _draft_with_two_teams()
    assert draft.can_claim(second.id, first.id) is True
    assert draft.can_claim(unit.id, first.id) is True
    # An unmodelled label may claim, matching the domain.
    assert draft.can_claim("Head of QA", first.id) is True
    assert draft.can_claim("", first.id) is False
    assert draft.can_claim(first.id, first.id) is False
    # A unit has no decision class, so it cannot be claimed.
    assert draft.can_claim(first.id, unit.id) is False


def test_add_claim_records_once_and_refuses_duplicates_and_illegals():
    draft, unit, first, second = _draft_with_two_teams()
    assert draft.add_claim(second.id, first.id) is True
    assert draft.add_claim(second.id, first.id) is False
    assert draft.add_claim(first.id, first.id) is False
    assert draft.claims_on(first.id) == (ClaimSpec(second.id, first.id),)


def test_remove_claim_drops_only_the_named_pair():
    draft, unit, first, second = _draft_with_two_teams()
    draft.add_claim(second.id, first.id)
    draft.add_claim(unit.id, first.id)
    draft.remove_claim(second.id, first.id)
    assert draft.claims_on(first.id) == (ClaimSpec(unit.id, first.id),)


def test_claimant_options_exclude_the_subject_itself():
    draft, unit, first, second = _draft_with_two_teams()
    option_ids = {ident for ident, _ in draft.claimant_options(first.id)}
    assert first.id not in option_ids
    assert {second.id, unit.id} <= option_ids


def test_removing_a_node_prunes_the_claims_it_carried():
    draft, unit, first, second = _draft_with_two_teams()
    draft.add_claim(second.id, first.id)
    draft.remove(second.id)
    assert draft.claims == ()


def test_removing_a_subject_prunes_its_claims():
    draft, unit, first, second = _draft_with_two_teams()
    draft.add_claim(second.id, first.id)
    draft.remove(first.id)
    assert draft.claims == ()


def test_converting_a_team_to_a_unit_drops_claims_on_it_but_not_by_it():
    draft, unit, first, second = _draft_with_two_teams()
    draft.add_claim(second.id, first.id)
    draft.add_claim(first.id, second.id)
    draft.convert_to_container(first.id, "Domain")
    assert draft.claims == (ClaimSpec(first.id, second.id),)


def test_claims_round_trip_through_the_blueprint():
    blueprint = OrgBlueprint(
        teams=make_blueprint().teams,
        dependencies=make_blueprint().dependencies,
        workload=make_blueprint().workload,
        domains=make_blueprint().domains,
        claims=(
            ClaimSpec("team_2", "team_1"),
            ClaimSpec("Head of QA", "team_2"),
        ),
    )
    draft = OrgDraft.from_blueprint(blueprint, NamePicker(Random(0)))
    assert draft.claims == blueprint.claims
    # The unmodelled claimant survives the round trip untouched.
    assert draft.to_blueprint().claims == blueprint.claims


def test_to_blueprint_drops_claims_whose_subject_no_longer_exists():
    draft = make_imported_draft()
    draft.remove("team_1")
    # Set after removal, so the harvest filter itself does the dropping.
    draft.claims = (ClaimSpec("team_2", "team_1"),)
    assert draft.to_blueprint().claims == ()


def test_blueprint_without_claims_yields_an_unclaimed_draft():
    draft = make_imported_draft()
    assert draft.claims == ()
    assert draft.to_blueprint().claims == ()
