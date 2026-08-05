"""Tests for the session record: snapshots, restore and move naming."""

from session_support import FakeSimulator as _FakeSimulator
from session_support import flat_org as _org
from session_support import nested_org as _nested_org

from fulcrum.application.dto import SessionSnapshot
from fulcrum.application.game_session import (
    GameSession,
    record_positions,
    restore_session,
)
from fulcrum.domain.hierarchy import TOP_LEVEL_FOCUS
from fulcrum.domain.moves import Move, MoveKind


def test_snapshot_captures_start_moves_and_result():
    session = GameSession(_org(), _FakeSimulator())
    session.play(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)))
    snapshot = session.snapshot()
    assert snapshot.initial_org == _org()
    assert snapshot.moves == session.history
    assert snapshot.org == session.org


def test_mark_history_as_prior_counts_and_take_back_clamps():
    session = GameSession(_org(), _FakeSimulator())
    session.play(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)))
    session.mark_history_as_prior()
    assert session.prior_history_count == 1
    session.play(Move(MoveKind.REALIGN_INCENTIVES, ("b",)))
    assert session.prior_history_count == 1
    session.take_back()
    assert session.prior_history_count == 1
    session.take_back()
    assert session.prior_history_count == 0
    assert session.history == ()


def test_restore_session_replays_and_rebuilds_the_undo_stack():
    original = GameSession(_org(), _FakeSimulator())
    original.play(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)))
    original.play(Move(MoveKind.REALIGN_INCENTIVES, ("b",)))
    restored = restore_session(original.snapshot(), _FakeSimulator())
    assert restored.org == original.org
    assert restored.history == original.history
    assert restored.prior_history_count == 2
    assert restored.can_take_back
    restored.take_back()
    restored.take_back()
    assert restored.org == _org()
    assert not restored.can_take_back


def test_restore_session_falls_back_when_a_move_cannot_replay():
    snapshot = SessionSnapshot(
        _org(), (Move(MoveKind.DELEGATE_AUTHORITY, ("ghost",)),), _org()
    )
    restored = restore_session(snapshot, _FakeSimulator())
    assert restored.org == _org()
    assert restored.history == ()
    assert restored.prior_history_count == 0


def test_the_drilled_section_is_carried_in_the_snapshot_and_restored():
    original = GameSession(_nested_org(), _FakeSimulator())
    original.focus("d1")
    assert original.snapshot().focused_on == "d1"
    restored = restore_session(original.snapshot(), _FakeSimulator())
    assert restored.focused_on == "d1"


def test_the_top_level_frame_is_restored_as_itself():
    original = GameSession(_nested_org(), _FakeSimulator())
    original.focus(TOP_LEVEL_FOCUS)
    restored = restore_session(original.snapshot(), _FakeSimulator())
    assert restored.focused_on == TOP_LEVEL_FOCUS


def test_an_unfocused_session_restores_unfocused():
    original = GameSession(_nested_org(), _FakeSimulator())
    assert original.snapshot().focused_on is None
    assert restore_session(original.snapshot(), _FakeSimulator()).focused_on is None


def test_a_focus_on_a_unit_that_is_gone_returns_to_the_whole_org():
    # The restored focus is validated against the org that came back, so a
    # file naming a unit this organisation does not have cannot leave the
    # session pointed at nothing.
    snapshot = SessionSnapshot(_nested_org(), (), _nested_org(), "ghost")
    assert restore_session(snapshot, _FakeSimulator()).focused_on is None


def test_the_focus_is_restored_even_when_the_moves_will_not_replay():
    snapshot = SessionSnapshot(
        _nested_org(),
        (Move(MoveKind.DELEGATE_AUTHORITY, ("ghost",)),),
        _nested_org(),
        "d1",
    )
    restored = restore_session(snapshot, _FakeSimulator())
    assert restored.history == ()
    assert restored.focused_on == "d1"


def test_played_moves_are_named_for_the_record():
    session = GameSession(_org(), _FakeSimulator())
    session.play(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)))
    assert session.history[0].label == "Delegate authority to B"
    already = Move(MoveKind.REALIGN_INCENTIVES, ("b",), "Custom label")
    session.play(already)
    assert session.history[1].label == "Custom label"


def test_a_frame_move_is_named_in_the_frame_it_was_played_in():
    """The record carries the text the player clicked, never the expansion.

    A delegate played on a rolled unit stores the unit's name as its
    label while its targets are the translated real teams, so the
    last-move note reads as the move the player chose rather than a
    wall of team names.
    """
    session = GameSession(_nested_org(), _FakeSimulator())
    session.focus("root")
    session.play(Move(MoveKind.DELEGATE_AUTHORITY, ("d1",)))
    assert session.history[0].label == "Delegate authority to Dept One"
    assert set(session.history[0].targets) == {"a", "b"}
    unfocused = GameSession(_nested_org(), _FakeSimulator())
    assert unfocused.try_play_in_frame(
        Move(MoveKind.DELEGATE_AUTHORITY, ("d1",)), "root"
    )
    assert unfocused.history[0].label == "Delegate authority to Dept One"


def test_a_pass_through_move_falls_back_to_naming_the_real_act():
    """A move whose names outrun its frame still gets an honest label."""
    session = GameSession(_nested_org(), _FakeSimulator())
    assert session.try_play_in_frame(Move(MoveKind.REALIGN_INCENTIVES, ("a",)), "root")
    assert session.history[0].label == "Realign incentives at A"


def test_a_top_level_move_is_named_as_its_rolled_unit():
    session = GameSession(_nested_org(), _FakeSimulator())
    assert session.try_play_in_frame(
        Move(MoveKind.DELEGATE_AUTHORITY, ("root",)), TOP_LEVEL_FOCUS
    )
    assert session.history[0].label == "Delegate authority to Org"


def test_record_positions_replays_every_position():
    """Position i is the org before history[i]; i + 1 the org after it."""
    session = GameSession(_org(), _FakeSimulator())
    session.play(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)))
    session.play(Move(MoveKind.REALIGN_INCENTIVES, ("a",)))
    positions = record_positions(session.initial_org, session.history)
    assert len(positions) == 3
    assert positions[0] == session.initial_org
    assert positions[0].team("b").has_local_authority is False
    assert positions[1].team("b").has_local_authority is True
    assert positions[2] == session.org
