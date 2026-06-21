"""The game session: current position, move history and scoring.

A session is a mutable coordinator. It owns no rules of its own; it composes the
pure domain (apply_move, signals) with an injected simulator and persists
through injected Protocols.
"""

from __future__ import annotations

from fulcrum.application.dto import MoveValuation, SavedGame
from fulcrum.application.interfaces import Clock, SaveGameRepository, Simulator
from fulcrum.domain.hierarchy import domain_has_teams, focused_suborg
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, MoveKind, apply_move
from fulcrum.domain.signals import SignalReading, compute_signals
from fulcrum.domain.simulation import coupling_of

# Growth moves are only offered to a team that carries enough dependencies for
# the move to mean something: a split needs two to share between the new owners,
# and adding an owner needs one to hand over.
_MIN_COUPLING_TO_SPLIT: int = 2
_MIN_COUPLING_TO_ADD_OWNER: int = 1

# The largest section scored and valuated live. Scoring is O(teams x deps) and
# valuating every candidate move repeats it per move, so above this a scope is an
# overview to drill into rather than a position to play, which keeps a hundred
# thousand person org responsive: you narrow to a section, and that section plays.
# Set so a single division's worth of teams still plays whole, and only larger
# scopes become an overview.
_MAX_PLAYABLE_TEAMS: int = 200


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
        self._focus_id: str | None = None

    @property
    def org(self) -> OrgState:
        return self._org

    @property
    def initial_org(self) -> OrgState:
        return self._initial_org

    @property
    def history(self) -> tuple[Move, ...]:
        return tuple(self._history)

    @property
    def focused_on(self) -> str | None:
        """The domain currently focused for scoring and play, or None."""
        return self._focus_id

    def focus(self, domain_id: str | None) -> None:
        """Focus scoring and the move palette on one domain's section.

        Drilling into a domain plays it as a self-contained section: the score,
        signals and candidate moves all reflect its focused sub-org, so a move
        that is only great within that section reads as great. Moves still apply
        to the whole org, so acting on a section's great move is real and
        permanent. Passing None, or a domain with no teams, returns to the whole
        org.
        """
        if domain_id is not None and not domain_has_teams(self._org, domain_id):
            domain_id = None
        self._focus_id = domain_id

    def _active_org(self) -> OrgState:
        """The org currently being scored: the focused section, or the whole."""
        if self._focus_id is None:
            return self._org
        return focused_suborg(self._org, self._focus_id)

    def score(self) -> float:
        return self._simulator.score(self._active_org()).value

    def signals(self) -> tuple[SignalReading, ...]:
        return compute_signals(self._active_org())

    def is_active_scope_playable(self) -> bool:
        """Whether the current scope is small enough to score and valuate live.

        Above the playable size the board shows the scope as an overview to drill
        into, since scoring and valuating the whole of a large org would stall.
        """
        return len(self._active_org().teams) <= _MAX_PLAYABLE_TEAMS

    def candidate_valuations(self) -> tuple[MoveValuation, ...]:
        active = self._active_org()
        if len(active.teams) > _MAX_PLAYABLE_TEAMS:
            return ()
        return self._simulator.valuate_moves(active, enumerate_moves(active))

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
