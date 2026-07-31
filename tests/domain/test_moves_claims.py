"""Tests for the authority-claim moves and claim handling in structural moves."""

import pytest

from fulcrum.domain.errors import InvalidMoveError, UnknownTeamError
from fulcrum.domain.models import AuthorityClaim, Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind, apply_move


def _t(team_id, authority=True, skew=0.0):
    return Team(
        id=team_id,
        name=team_id.upper(),
        has_local_authority=authority,
        incentive_skew=skew,
    )


def _contested_org():
    return OrgState(
        teams=(_t("a"), _t("b", authority=False)),
        workload=2,
        domains=(Domain("unit", "Unit"),),
        claims=(
            AuthorityClaim("b", "a"),
            AuthorityClaim("unit", "a"),
            AuthorityClaim("Head of QA", "b"),
        ),
    )


def test_resolve_in_favour_of_the_team_grants_authority_and_clears_claims():
    after = apply_move(_contested_org(), Move(MoveKind.RESOLVE_AUTHORITY, ("a", "a")))
    assert after.team("a").has_local_authority is True
    assert after.claims_on("a") == ()
    # Claims on other subjects are untouched.
    assert after.claims_on("b") == (AuthorityClaim("Head of QA", "b"),)


def test_resolve_in_favour_of_a_claimant_clears_the_contest():
    after = apply_move(
        _contested_org(), Move(MoveKind.RESOLVE_AUTHORITY, ("a", "unit"))
    )
    # The transfer is complete: no standing claim remains, the class now
    # escalates to its new owner cleanly.
    assert after.team("a").has_local_authority is False
    assert after.claims_on("a") == ()


def test_resolve_accepts_an_unmodelled_claimant_as_winner():
    after = apply_move(
        _contested_org(), Move(MoveKind.RESOLVE_AUTHORITY, ("b", "Head of QA"))
    )
    assert after.team("b").has_local_authority is False
    assert after.claims_on("b") == ()


def test_resolve_validates_its_targets():
    org = _contested_org()
    with pytest.raises(InvalidMoveError):
        apply_move(org, Move(MoveKind.RESOLVE_AUTHORITY, ("a",)))
    with pytest.raises(UnknownTeamError):
        apply_move(org, Move(MoveKind.RESOLVE_AUTHORITY, ("ghost", "ghost")))
    with pytest.raises(InvalidMoveError):
        apply_move(org, Move(MoveKind.RESOLVE_AUTHORITY, ("a", "Head of QA")))


def test_downgrade_turns_a_modelled_claim_into_a_consulted_dependency():
    after = apply_move(_contested_org(), Move(MoveKind.DOWNGRADE_CLAIM, ("b", "a")))
    assert AuthorityClaim("b", "a") not in after.claims
    assert Dependency("b", "a", 1) in after.dependencies


def test_downgrade_by_a_unit_creates_a_unit_dependency():
    after = apply_move(_contested_org(), Move(MoveKind.DOWNGRADE_CLAIM, ("unit", "a")))
    assert Dependency("unit", "a", 1) in after.dependencies


def test_downgrade_does_not_duplicate_an_existing_dependency():
    org = OrgState(
        teams=(_t("a"), _t("b")),
        dependencies=(Dependency("b", "a", 3),),
        claims=(AuthorityClaim("b", "a"),),
    )
    after = apply_move(org, Move(MoveKind.DOWNGRADE_CLAIM, ("b", "a")))
    assert after.dependencies == (Dependency("b", "a", 3),)
    assert after.claims == ()


def test_downgrade_of_an_unmodelled_claimant_just_removes_the_claim():
    after = apply_move(
        _contested_org(), Move(MoveKind.DOWNGRADE_CLAIM, ("Head of QA", "b"))
    )
    assert after.claims_on("b") == ()
    assert not any(d.upstream == "Head of QA" for d in after.dependencies)


def test_downgrade_validates_its_targets():
    org = _contested_org()
    with pytest.raises(InvalidMoveError):
        apply_move(org, Move(MoveKind.DOWNGRADE_CLAIM, ("b",)))
    with pytest.raises(InvalidMoveError):
        apply_move(org, Move(MoveKind.DOWNGRADE_CLAIM, ("unit", "b")))


def test_matrix_overlay_contests_every_team():
    org = OrgState(teams=(_t("a"), _t("b")), workload=1)
    after = apply_move(org, Move(MoveKind.IMPOSE_MATRIX_OVERLAY))
    # The overlay is an unmodelled claimant beside the delivery graph, not
    # a team: it neither dilutes per-team means nor absorbs escalated load.
    assert not after.has_team("overlay_1")
    assert len(after.teams) == len(org.teams)
    assert AuthorityClaim("overlay_1", "a") in after.claims
    assert AuthorityClaim("overlay_1", "b") in after.claims


def test_second_overlay_gets_a_fresh_id():
    org = OrgState(teams=(_t("a"),), workload=1)
    once = apply_move(org, Move(MoveKind.IMPOSE_MATRIX_OVERLAY))
    twice = apply_move(once, Move(MoveKind.IMPOSE_MATRIX_OVERLAY))
    assert AuthorityClaim("overlay_2", "a") in twice.claims


def test_collapse_remaps_claims_and_drops_self_claims_and_duplicates():
    org = OrgState(
        teams=(_t("keep"), _t("drop"), _t("other", authority=False)),
        dependencies=(Dependency("keep", "drop", 1),),
        claims=(
            AuthorityClaim("drop", "other"),
            AuthorityClaim("keep", "other"),
            AuthorityClaim("drop", "keep"),
            AuthorityClaim("chapter", "drop"),
        ),
    )
    after = apply_move(org, Move(MoveKind.COLLAPSE_BOUNDARY, ("keep", "drop")))
    # drop's claim on other merges into keep's identical claim (one survives);
    # drop's claim on keep becomes a self-claim and vanishes; the chapter's
    # claim follows the merged subject.
    assert after.claims == (
        AuthorityClaim("keep", "other"),
        AuthorityClaim("chapter", "keep"),
    )


def test_structural_moves_carry_claims_through():
    org = OrgState(
        teams=(_t("a", authority=False, skew=0.4), _t("b")),
        dependencies=(Dependency("a", "b", 2),),
        workload=2,
        claims=(AuthorityClaim("chapter", "b"),),
    )
    for move in (
        Move(MoveKind.ADD_APPROVAL_LAYER),
        Move(MoveKind.STABILISE_INTERFACES),
        Move(MoveKind.DELEGATE_AUTHORITY, ("a",)),
        Move(MoveKind.REALIGN_INCENTIVES, ("a",)),
        Move(MoveKind.SPLIT_TEAM, ("a",)),
        Move(MoveKind.ADD_TEAM, ("a",)),
    ):
        after = apply_move(org, move)
        assert AuthorityClaim("chapter", "b") in after.claims
