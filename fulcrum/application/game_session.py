"""The game session: current position, move history and scoring.

A session is a mutable coordinator. It owns no rules of its own; it composes the
pure domain (apply_move, signals) with an injected simulator and persists
through injected Protocols.
"""

from __future__ import annotations

from fulcrum.application.dto import MoveValuation, SavedGame
from fulcrum.application.interfaces import Clock, SaveGameRepository, Simulator
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, MoveKind, apply_move
from fulcrum.domain.signals import SignalReading, compute_signals
from fulcrum.domain.simulation import coupling_of

# Growth moves are only offered to a team that carries enough dependencies for
# the move to mean something: a split needs two to share between the new owners,
# and adding an owner needs one to hand over.
_MIN_COUPLING_TO_SPLIT: int = 2
_MIN_COUPLING_TO_ADD_OWNER: int = 1


def enumerate_moves(org: OrgState, allow_growth: bool = False) -> tuple[Move, ...]:
    """List the candidate moves offered for an org, including the blunder.

    With allow_growth set, the org may also grow: an overloaded team can split
    into two owners, or hand part of its load to a newly created owner. This is
    the path the guide takes when the player asks to let the org grow.
    """
    moves: list[Move] = []
    for team in org.teams:
        if not team.has_local_authority:
            moves.append(Move(MoveKind.DELEGATE_AUTHORITY, (team.id,)))
        if team.incentive_skew > 0:
            moves.append(Move(MoveKind.REALIGN_INCENTIVES, (team.id,)))
    if org.dependencies:
        moves.append(Move(MoveKind.STABILISE_INTERFACES))
    for dep in org.dependencies:
        moves.append(Move(MoveKind.COLLAPSE_BOUNDARY, (dep.upstream, dep.downstream)))
    moves.append(Move(MoveKind.ADD_APPROVAL_LAYER))
    if allow_growth:
        _append_growth_moves(org, moves)
    return tuple(moves)


def _append_growth_moves(org: OrgState, moves: list[Move]) -> None:
    for team in org.teams:
        coupling = coupling_of(org, team.id)
        if coupling >= _MIN_COUPLING_TO_SPLIT:
            moves.append(Move(MoveKind.SPLIT_TEAM, (team.id,)))
        if coupling >= _MIN_COUPLING_TO_ADD_OWNER:
            moves.append(Move(MoveKind.ADD_TEAM, (team.id,)))


class GameSession:
    """Coordinates an org state with an injected simulator and persistence."""

    def __init__(self, org: OrgState, simulator: Simulator) -> None:
        self._org = org
        self._initial_org = org
        self._simulator = simulator
        self._history: list[Move] = []

    @property
    def org(self) -> OrgState:
        return self._org

    @property
    def initial_org(self) -> OrgState:
        return self._initial_org

    @property
    def history(self) -> tuple[Move, ...]:
        return tuple(self._history)

    def score(self) -> float:
        return self._simulator.score(self._org).value

    def signals(self) -> tuple[SignalReading, ...]:
        return compute_signals(self._org)

    def candidate_valuations(self) -> tuple[MoveValuation, ...]:
        return self._simulator.valuate_moves(self._org, enumerate_moves(self._org))

    def play(self, move: Move) -> None:
        self._org = apply_move(self._org, move)
        self._history.append(move)

    def preview(self, move: Move) -> OrgState:
        return apply_move(self._org, move)

    def to_saved_game(self, clock: Clock) -> SavedGame:
        return SavedGame(
            org=self._org, history=self.history, created_at=clock.timestamp()
        )

    def save(self, repository: SaveGameRepository, slot: str, clock: Clock) -> None:
        repository.save(slot, self.to_saved_game(clock))

    @classmethod
    def from_saved_game(cls, game: SavedGame, simulator: Simulator) -> "GameSession":
        session = cls(game.org, simulator)
        session._history = list(game.history)
        return session
