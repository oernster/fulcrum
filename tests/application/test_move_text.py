"""Tests for human-readable move descriptions."""

from fulcrum.application.move_text import describe_move, move_note
from fulcrum.domain.models import Dependency, OrgState, Team
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


def test_move_note_covers_every_kind():
    for kind in MoveKind:
        assert move_note(kind)
    assert "not centralisation" in move_note(MoveKind.COLLAPSE_BOUNDARY)
    assert "blunder" in move_note(MoveKind.ADD_APPROVAL_LAYER)
