"""Tests for authority claims: the value object, scoring and frame projection."""

import pytest

from fulcrum.domain.errors import InvalidOrgStateError
from fulcrum.domain.hierarchy import focused_suborg
from fulcrum.domain.models import AuthorityClaim, Dependency, Domain, OrgState, Team
from fulcrum.domain.simulation import (
    SimulationParameters,
    claim_load,
    dependency_index,
    evaluate,
    external_claimants,
    is_contested,
    team_capacity,
)


def _t(team_id, authority=True, skew=0.0, domain_id=None):
    return Team(
        id=team_id,
        name=team_id.upper(),
        has_local_authority=authority,
        incentive_skew=skew,
        domain_id=domain_id,
    )


def test_claim_endpoints_must_be_non_empty():
    with pytest.raises(InvalidOrgStateError):
        AuthorityClaim("", "a")
    with pytest.raises(InvalidOrgStateError):
        AuthorityClaim("a", "")


def test_a_team_cannot_claim_itself():
    with pytest.raises(InvalidOrgStateError):
        AuthorityClaim("a", "a")


def test_claim_subject_must_be_a_known_team():
    with pytest.raises(InvalidOrgStateError):
        OrgState(teams=(_t("a"),), claims=(AuthorityClaim("chapter", "ghost"),))


def test_duplicate_claims_are_rejected():
    with pytest.raises(InvalidOrgStateError):
        OrgState(
            teams=(_t("a"),),
            claims=(
                AuthorityClaim("chapter", "a"),
                AuthorityClaim("chapter", "a"),
            ),
        )


def test_claims_on_returns_only_the_subjects_claims():
    org = OrgState(
        teams=(_t("a"), _t("b")),
        claims=(AuthorityClaim("chapter", "a"), AuthorityClaim("chapter", "b")),
    )
    assert org.claims_on("a") == (AuthorityClaim("chapter", "a"),)


def test_any_standing_claim_makes_a_team_contested():
    # The structural owner (the team, or the line it escalates to) is always
    # claimant one, so a claim contests a local decider and an escalating
    # team alike; only an unclaimed team is uncontested.
    org = OrgState(
        teams=(_t("a", authority=True), _t("b", authority=False), _t("c")),
        claims=(AuthorityClaim("chapter", "a"), AuthorityClaim("chapter", "b")),
    )
    assert is_contested(org, org.team("a")) is True
    assert is_contested(org, org.team("b")) is True
    assert is_contested(org, org.team("c")) is False


def test_external_claimants_with_and_without_the_index():
    org = OrgState(
        teams=(_t("a"), _t("b")),
        claims=(AuthorityClaim("x", "a"), AuthorityClaim("y", "a")),
    )
    index = dependency_index(org)
    assert external_claimants(org, "a") == 2
    assert external_claimants(org, "a", index) == 2
    assert external_claimants(org, "b", index) == 0


def test_claim_load_counts_one_excess_claimant_per_standing_claim():
    org = OrgState(
        teams=(_t("a", authority=True), _t("b", authority=False)),
        claims=(
            AuthorityClaim("x", "a"),
            AuthorityClaim("x", "b"),
            AuthorityClaim("y", "b"),
        ),
    )
    # Each standing claim is one claimant beyond the structural owner.
    assert claim_load(org) == 3.0


def test_contested_capacity_is_never_above_clean_escalation():
    contested = OrgState(
        teams=(_t("a", authority=True),), claims=(AuthorityClaim("x", "a"),)
    )
    escalating = OrgState(teams=(_t("a", authority=False),))
    contested_cap = team_capacity(contested, contested.team("a"))
    escalating_cap = team_capacity(escalating, escalating.team("a"))
    assert contested_cap <= escalating_cap


def test_a_contested_team_counts_in_the_escalation_share():
    healthy = OrgState(teams=(_t("a"), _t("b")))
    contested = OrgState(teams=(_t("a"), _t("b")), claims=(AuthorityClaim("x", "a"),))
    assert evaluate(contested).escalation_penalty > evaluate(healthy).escalation_penalty


def test_contest_lowers_the_score_and_scales_with_claimants():
    base = OrgState(teams=(_t("a"), _t("b")), workload=1)
    one = OrgState(
        teams=(_t("a"), _t("b")),
        workload=1,
        claims=(AuthorityClaim("x", "a"),),
    )
    two = OrgState(
        teams=(_t("a"), _t("b")),
        workload=1,
        claims=(AuthorityClaim("x", "a"), AuthorityClaim("y", "a")),
    )
    assert evaluate(one).value < evaluate(base).value
    assert evaluate(two).value < evaluate(one).value


def test_no_claims_leaves_the_score_untouched():
    org = OrgState(
        teams=(_t("a"), _t("b", authority=False, skew=0.3)),
        dependencies=(Dependency("a", "b", 2),),
        workload=3,
    )
    frozen = SimulationParameters(contested_weight=0.0, contested_penalty=0.45)
    assert evaluate(org).value == evaluate(org, frozen).value


def test_contested_penalty_must_not_exceed_the_authority_penalty():
    with pytest.raises(InvalidOrgStateError):
        SimulationParameters(contested_penalty=0.5, authority_penalty=0.45)
    with pytest.raises(InvalidOrgStateError):
        SimulationParameters(contested_penalty=0.0)


def test_contested_weight_must_not_be_negative():
    with pytest.raises(InvalidOrgStateError):
        SimulationParameters(contested_weight=-0.1)


def test_leaf_frame_carries_claims_on_its_own_teams():
    org = OrgState(
        teams=(_t("a", domain_id="d1"), _t("b", domain_id="d2")),
        workload=1,
        domains=(Domain("d1", "One"), Domain("d2", "Two")),
        claims=(AuthorityClaim("outside", "a"), AuthorityClaim("outside", "b")),
    )
    section = focused_suborg(org, "d1")
    assert section.claims == (AuthorityClaim("outside", "a"),)
    assert is_contested(section, section.team("a")) is True
