"""Tests for the pure plan-edit operations."""

from fulcrum.application import plan_edit
from fulcrum.domain.models import Dependency, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind


def _org():
    return OrgState(
        teams=(Team("a", "Alpha", False, 0.0), Team("b", "Bravo", True, 0.0)),
        dependencies=(Dependency("a", "b", 2),),
        workload=3,
    )


_VALID = (
    Move(MoveKind.SPLIT_TEAM, ("a",)),
    Move(MoveKind.DELEGATE_AUTHORITY, ("a_b",)),
)


def test_without_move_removes_by_index():
    out = plan_edit.without_move(_VALID, 0)
    assert out == (_VALID[1],)


def test_moved_up_swaps_or_noops_at_top():
    assert plan_edit.moved_up(_VALID, 1) == (_VALID[1], _VALID[0])
    assert plan_edit.moved_up(_VALID, 0) == _VALID


def test_moved_down_swaps_or_noops_at_bottom():
    assert plan_edit.moved_down(_VALID, 0) == (_VALID[1], _VALID[0])
    assert plan_edit.moved_down(_VALID, 1) == _VALID


def test_first_invalid_index_finds_the_break_or_none():
    assert plan_edit.first_invalid_index(_org(), _VALID) is None
    broken = (Move(MoveKind.DELEGATE_AUTHORITY, ("a_b",)),)
    assert plan_edit.first_invalid_index(_org(), broken) == 0


def test_annotate_describes_and_flags_the_break():
    valid_rows = plan_edit.annotate(_org(), _VALID)
    assert all(ok for _, ok in valid_rows)

    sequence = (
        Move(MoveKind.DELEGATE_AUTHORITY, ("b",)),
        Move(MoveKind.DELEGATE_AUTHORITY, ("a_b",)),
        Move(MoveKind.STABILISE_INTERFACES),
    )
    rows = plan_edit.annotate(_org(), sequence)
    assert rows[0][1] is True
    assert rows[1][1] is False
    assert rows[2][1] is False
