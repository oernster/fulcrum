"""Tests for human-readable move descriptions."""

from fulcrum.application.move_text import describe_move, move_note
from fulcrum.domain.models import AuthorityClaim, Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind


def _org():
    return OrgState(
        teams=(Team("a", "Alpha", False, 0.5), Team("b", "Bravo", False, 0.4)),
        dependencies=(Dependency("a", "b", 3),),
        workload=4,
    )


def test_describe_each_kind():
    org = _org()
    assert (
        describe_move(org, Move(MoveKind.DELEGATE_AUTHORITY, ("a",)))
        == "Delegate authority to Alpha"
    )
    assert (
        describe_move(org, Move(MoveKind.REALIGN_INCENTIVES, ("b",)))
        == "Realign incentives at Bravo"
    )
    assert (
        describe_move(org, Move(MoveKind.COLLAPSE_BOUNDARY, ("a", "b")))
        == "Collapse Alpha + Bravo"
    )
    assert (
        describe_move(org, Move(MoveKind.STABILISE_INTERFACES))
        == "Stabilise all interfaces"
    )
    assert (
        describe_move(org, Move(MoveKind.ADD_APPROVAL_LAYER)) == "Add an approval layer"
    )


def test_describe_growth_kinds():
    org = _org()
    assert (
        describe_move(org, Move(MoveKind.SPLIT_TEAM, ("a",)))
        == "Split Alpha into two owners"
    )
    assert (
        describe_move(org, Move(MoveKind.ADD_TEAM, ("b",)))
        == "Add a new owner beside Bravo"
    )


def _claimed_org():
    return OrgState(
        teams=(Team("a", "Alpha", True, 0.0), Team("b", "Bravo", True, 0.0)),
        workload=1,
        domains=(Domain("unit", "Platform Unit"),),
        claims=(
            AuthorityClaim("b", "a"),
            AuthorityClaim("unit", "a"),
            AuthorityClaim("Head of QA", "a"),
        ),
    )


def test_describe_claim_kinds():
    org = _claimed_org()
    assert (
        describe_move(org, Move(MoveKind.RESOLVE_AUTHORITY, ("a", "a")))
        == "Resolve authority at Alpha in its favour"
    )
    assert (
        describe_move(org, Move(MoveKind.RESOLVE_AUTHORITY, ("a", "b")))
        == "Resolve authority at Alpha in favour of Bravo"
    )
    assert (
        describe_move(org, Move(MoveKind.RESOLVE_AUTHORITY, ("a", "unit")))
        == "Resolve authority at Alpha in favour of Platform Unit"
    )
    assert (
        describe_move(org, Move(MoveKind.RESOLVE_AUTHORITY, ("a", "Head of QA")))
        == "Resolve authority at Alpha in favour of Head of QA"
    )
    assert (
        describe_move(org, Move(MoveKind.DOWNGRADE_CLAIM, ("unit", "a")))
        == "Downgrade Platform Unit's claim on Alpha to consultation"
    )
    assert (
        describe_move(org, Move(MoveKind.IMPOSE_MATRIX_OVERLAY))
        == "Impose a matrix overlay"
    )


def test_move_note_covers_every_kind():
    for kind in MoveKind:
        assert move_note(kind)
    assert "not centralisation" in move_note(MoveKind.COLLAPSE_BOUNDARY)
    assert "blunder" in move_note(MoveKind.ADD_APPROVAL_LAYER)
