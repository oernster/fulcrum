"""Tests for the game session coordinator, using Protocol fakes."""

from fulcrum.application.dto import MoveValuation, SavedGame
from fulcrum.application.game_session import GameSession, enumerate_moves
from fulcrum.domain.models import Dependency, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind
from fulcrum.domain.simulation import MoveClassification, StructuralScore


class _FakeSimulator:
    def score(self, org):
        return StructuralScore(50.0, 0.0, 0.0, 0.0)

    def valuate_moves(self, org, moves):
        return tuple(
            MoveValuation(m, 50.0, 55.0, MoveClassification.GOOD) for m in moves
        )


class _FakeClock:
    def timestamp(self):
        return "2026-06-17T12:00:00"


class _FakeRepository:
    def __init__(self):
        self.saved = {}

    def save(self, slot, game):
        self.saved[slot] = game

    def load(self, slot):
        return self.saved[slot]

    def slots(self):
        return tuple(self.saved)


def _org():
    return OrgState(
        teams=(Team("a", "A", True, 0.0), Team("b", "B", False, 0.5)),
        dependencies=(Dependency("a", "b", 3),),
        workload=2,
    )


def test_enumerate_moves_offers_each_kind():
    kinds = {m.kind for m in enumerate_moves(_org())}
    assert MoveKind.DELEGATE_AUTHORITY in kinds
    assert MoveKind.REALIGN_INCENTIVES in kinds
    assert MoveKind.STABILISE_INTERFACES in kinds
    assert MoveKind.COLLAPSE_BOUNDARY in kinds
    assert MoveKind.ADD_APPROVAL_LAYER in kinds


def test_enumerate_moves_without_dependencies():
    org = OrgState(teams=(Team("a", "A", True, 0.0),), workload=1)
    assert tuple(m.kind for m in enumerate_moves(org)) == (MoveKind.ADD_APPROVAL_LAYER,)


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


def test_game_session_flow():
    session = GameSession(_org(), _FakeSimulator())
    assert session.score() == 50.0
    assert len(session.signals()) == 4
    assert len(session.candidate_valuations()) == len(enumerate_moves(_org()))
    session.play(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)))
    assert session.org.team("b").has_local_authority is True
    assert session.initial_org.team("b").has_local_authority is False
    assert session.history[0].kind == MoveKind.DELEGATE_AUTHORITY


def test_game_session_save_and_restore():
    session = GameSession(_org(), _FakeSimulator())
    session.play(Move(MoveKind.STABILISE_INTERFACES))
    repository = _FakeRepository()
    session.save(repository, "slot1", _FakeClock())
    saved = repository.load("slot1")
    assert isinstance(saved, SavedGame)
    assert saved.created_at == "2026-06-17T12:00:00"
    restored = GameSession.from_saved_game(saved, _FakeSimulator())
    assert restored.history == session.history
    assert restored.org == session.org


def test_preview_does_not_mutate_the_session():
    session = GameSession(_org(), _FakeSimulator())
    previewed = session.preview(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)))
    assert previewed.team("b").has_local_authority is True
    assert session.org.team("b").has_local_authority is False
