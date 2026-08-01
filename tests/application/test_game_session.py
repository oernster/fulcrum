"""Tests for the game session coordinator, using Protocol fakes."""

from session_support import FakeSimulator as _FakeSimulator
from session_support import flat_org as _org
from session_support import nested_org as _nested_org

from fulcrum.application.game_session import (
    MAX_PLAYABLE_TEAMS,
    GameSession,
    enumerate_moves,
)
from fulcrum.domain.hierarchy import TOP_LEVEL_FOCUS
from fulcrum.domain.models import AuthorityClaim, Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind


def test_enumerate_moves_offers_each_kind():
    kinds = {m.kind for m in enumerate_moves(_org())}
    assert MoveKind.DELEGATE_AUTHORITY in kinds
    assert MoveKind.REALIGN_INCENTIVES in kinds
    assert MoveKind.STABILISE_INTERFACES in kinds
    assert MoveKind.COLLAPSE_BOUNDARY in kinds
    assert MoveKind.ADD_APPROVAL_LAYER in kinds


def test_enumerate_moves_without_dependencies():
    org = OrgState(teams=(Team("a", "A", True, 0.0),), workload=1)
    assert tuple(m.kind for m in enumerate_moves(org)) == (
        MoveKind.ADD_APPROVAL_LAYER,
        MoveKind.IMPOSE_MATRIX_OVERLAY,
    )


def test_enumerate_moves_always_offers_both_blunders():
    kinds = tuple(m.kind for m in enumerate_moves(_org()))
    assert MoveKind.ADD_APPROVAL_LAYER in kinds
    assert MoveKind.IMPOSE_MATRIX_OVERLAY in kinds


def test_a_contested_team_gets_resolve_moves_instead_of_delegate():
    org = OrgState(
        teams=(Team("a", "A", True, 0.0), Team("b", "B", True, 0.0)),
        workload=1,
        domains=(Domain("unit", "Unit"),),
        claims=(
            AuthorityClaim("b", "a"),
            AuthorityClaim("unit", "a"),
            AuthorityClaim("Head of QA", "a"),
        ),
    )
    moves = enumerate_moves(org)
    resolve = {m.targets for m in moves if m.kind == MoveKind.RESOLVE_AUTHORITY}
    downgrade = {m.targets for m in moves if m.kind == MoveKind.DOWNGRADE_CLAIM}
    assert resolve == {
        ("a", "a"),
        ("a", "b"),
        ("a", "unit"),
        ("a", "Head of QA"),
    }
    # Downgrade is only offered for modelled claimants; the unmodelled label
    # is dealt with by resolving instead.
    assert downgrade == {("b", "a"), ("unit", "a")}
    assert MoveKind.DELEGATE_AUTHORITY not in {m.kind for m in moves}


def test_a_single_claim_team_gets_resolve_moves_for_both_endings():
    org = OrgState(
        teams=(Team("a", "A", False, 0.0), Team("b", "B", True, 0.0)),
        workload=1,
        claims=(AuthorityClaim("b", "a"),),
    )
    moves = enumerate_moves(org)
    resolve = {m.targets for m in moves if m.kind == MoveKind.RESOLVE_AUTHORITY}
    assert resolve == {("a", "a"), ("a", "b")}
    assert MoveKind.DELEGATE_AUTHORITY not in {m.kind for m in moves}


def test_enumerate_moves_growth_is_opt_in():
    org = OrgState(
        teams=(
            Team("a", "A", True, 0.0),
            Team("b", "B", True, 0.0),
            Team("c", "C", True, 0.0),
        ),
        dependencies=(Dependency("a", "b", 2), Dependency("a", "c", 2)),
        workload=2,
    )
    fixed = {m.kind for m in enumerate_moves(org)}
    assert MoveKind.SPLIT_TEAM not in fixed
    assert MoveKind.ADD_TEAM not in fixed
    grown = enumerate_moves(org, allow_growth=True)
    split_targets = {m.targets for m in grown if m.kind == MoveKind.SPLIT_TEAM}
    add_targets = {m.targets for m in grown if m.kind == MoveKind.ADD_TEAM}
    assert split_targets == {("a",)}
    assert add_targets == {("a",), ("b",), ("c",)}


def test_session_exposes_its_simulator():
    simulator = _FakeSimulator()
    assert GameSession(_org(), simulator).simulator is simulator


def test_game_session_flow():
    session = GameSession(_org(), _FakeSimulator())
    assert session.score() == 50.0
    assert len(session.signals()) == 7
    assert len(session.candidate_valuations()) == len(enumerate_moves(_org()))
    session.play(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)))
    assert session.org.team("b").has_local_authority is True
    assert session.initial_org.team("b").has_local_authority is False
    assert session.history[0].kind == MoveKind.DELEGATE_AUTHORITY


def test_preview_does_not_mutate_the_session():
    session = GameSession(_org(), _FakeSimulator())
    previewed = session.preview(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)))
    assert previewed.team("b").has_local_authority is True
    assert session.org.team("b").has_local_authority is False


def _domained_org():
    return OrgState(
        teams=(
            Team("a", "A", True, 0.0, domain_id="d1"),
            Team("b", "B", False, 0.5, domain_id="d1"),
            Team("c", "C", True, 0.0, domain_id="d2"),
        ),
        dependencies=(Dependency("a", "b", 3), Dependency("a", "c", 2)),
        workload=2,
        domains=(Domain("d1", "Platform"), Domain("d2", "Data")),
    )


def test_focus_scores_only_the_section():
    session = GameSession(_domained_org(), _FakeSimulator())
    assert session.focused_on is None
    full_moves = len(session.candidate_valuations())
    session.focus("d1")
    assert session.focused_on == "d1"
    assert len(session.candidate_valuations()) < full_moves
    assert len(session.signals()) == 7
    assert session.score() == 50.0


def test_focus_on_a_domain_without_teams_returns_to_the_whole_org():
    org = OrgState(
        teams=(Team("a", "A", True, 0.0, domain_id="d1"),),
        domains=(Domain("d1", "Platform"), Domain("d2", "Data")),
    )
    session = GameSession(org, _FakeSimulator())
    session.focus("d2")
    assert session.focused_on is None


def test_clearing_focus_restores_the_whole_org_palette():
    session = GameSession(_domained_org(), _FakeSimulator())
    session.focus("d1")
    session.focus(None)
    assert session.focused_on is None
    assert len(session.candidate_valuations()) == len(enumerate_moves(_domained_org()))


def test_a_focused_move_applies_to_the_whole_org_and_keeps_focus():
    session = GameSession(_domained_org(), _FakeSimulator())
    session.focus("d1")
    session.play(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)))
    assert session.org.team("b").has_local_authority is True
    assert session.focused_on == "d1"


def test_small_scope_is_playable_and_valuates():
    session = GameSession(_org(), _FakeSimulator())
    assert session.is_active_scope_playable() is True
    assert len(session.candidate_valuations()) == len(enumerate_moves(_org()))


def test_large_scope_is_not_playable_and_skips_valuation():
    teams = tuple(
        Team(f"t{i}", f"T{i}", True, 0.0) for i in range(MAX_PLAYABLE_TEAMS + 1)
    )
    session = GameSession(OrgState(teams=teams, workload=1), _FakeSimulator())
    assert session.is_active_scope_playable() is False
    assert session.candidate_valuations() == ()


def test_aggregate_scope_offers_only_translatable_moves():
    session = GameSession(_nested_org(), _FakeSimulator())
    session.focus("root")
    kinds = {v.move.kind for v in session.candidate_valuations()}
    assert kinds <= {
        MoveKind.DELEGATE_AUTHORITY,
        MoveKind.REALIGN_INCENTIVES,
        MoveKind.STABILISE_INTERFACES,
    }


def test_playing_an_aggregate_move_empowers_the_real_teams():
    session = GameSession(_nested_org(), _FakeSimulator())
    session.focus("root")
    session.play(Move(MoveKind.DELEGATE_AUTHORITY, ("d1",)))
    assert session.org.team("a").has_local_authority is True
    assert session.org.team("b").has_local_authority is True
    assert session.focused_on == "root"


def test_take_back_restores_the_previous_position():
    session = GameSession(_org(), _FakeSimulator())
    session.play(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)))
    assert session.org.team("b").has_local_authority is True
    assert session.can_take_back is True
    session.take_back()
    assert session.org.team("b").has_local_authority is False
    assert session.history == ()
    assert session.can_take_back is False


def test_take_back_walks_back_to_the_start():
    session = GameSession(_org(), _FakeSimulator())
    session.play(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)))
    session.play(Move(MoveKind.STABILISE_INTERFACES))
    assert len(session.history) == 2
    session.take_back()
    session.take_back()
    assert session.history == ()
    assert session.org == session.initial_org
    assert session.can_take_back is False


def test_take_back_with_no_history_is_a_no_op():
    session = GameSession(_org(), _FakeSimulator())
    assert session.can_take_back is False
    session.take_back()
    assert session.history == ()
    assert session.org == session.initial_org


def test_try_play_applies_a_valid_move():
    session = GameSession(_org(), _FakeSimulator())
    assert session.try_play(Move(MoveKind.DELEGATE_AUTHORITY, ("b",))) is True
    assert session.org.team("b").has_local_authority is True
    assert session.history[0].kind == MoveKind.DELEGATE_AUTHORITY
    assert session.can_take_back is True


def test_try_play_in_frame_translates_against_the_named_frame():
    # The session stays unfocused; the move still translates against the
    # explicit frame, which is how the hierarchy guide plays a unit's row.
    session = GameSession(_nested_org(), _FakeSimulator())
    assert session.focused_on is None
    assert session.try_play_in_frame(Move(MoveKind.DELEGATE_AUTHORITY, ("d1",)), "root")
    assert session.org.team("a").has_local_authority is True
    assert session.org.team("b").has_local_authority is True
    # d2's team is untouched: the move named d1 only.
    assert session.org.team("c") == _nested_org().team("c")


def test_try_play_rejects_a_move_with_an_unknown_target():
    session = GameSession(_org(), _FakeSimulator())
    assert session.try_play(Move(MoveKind.DELEGATE_AUTHORITY, ("ghost",))) is False
    assert session.history == ()
    assert session.can_take_back is False
    assert session.org == session.initial_org


def test_focus_top_level_offers_no_moves_but_still_translates_a_play():
    org = OrgState(
        teams=(
            Team("a", "A", False, 0.0, domain_id="r1"),
            Team("b", "B", False, 0.0, domain_id="r1"),
            Team("free", "Free", False, 0.0),
        ),
        dependencies=(Dependency("r1", "free", 3),),
        workload=2,
        domains=(Domain("r1", "One"),),
    )
    session = GameSession(org, _FakeSimulator())
    session.focus(TOP_LEVEL_FOCUS)
    assert session.focused_on == TOP_LEVEL_FOCUS
    # Nothing sits above the top level with the authority to make a move,
    # so the top frame's palette is empty; translation stays intact for
    # any caller that names the frame directly.
    assert session.candidate_valuations() == ()
    session.play(Move(MoveKind.DELEGATE_AUTHORITY, ("r1",)))
    assert session.org.team("a").has_local_authority
    assert session.org.team("b").has_local_authority
    assert not session.org.team("free").has_local_authority


def test_focus_top_level_falls_back_to_flat_without_domains():
    session = GameSession(_org(), _FakeSimulator())
    session.focus(TOP_LEVEL_FOCUS)
    assert session.focused_on is None
