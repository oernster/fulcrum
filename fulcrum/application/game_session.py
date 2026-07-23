"""The game session: current position, move history and scoring.

A session is a mutable coordinator. It owns no rules of its own; it composes the
pure domain (apply_move, signals) with an injected simulator.
"""

from __future__ import annotations

from fulcrum.application.dto import MoveValuation
from fulcrum.application.interfaces import Simulator
from fulcrum.domain.errors import FulcrumError
from fulcrum.domain.hierarchy import (
    AGGREGATE_MOVE_KINDS,
    child_domains,
    domain_has_teams,
    focused_suborg,
    translate_focused_move,
)
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, MoveKind, apply_move
from fulcrum.domain.signals import SignalReading, compute_signals
from fulcrum.domain.simulation import coupling_of

# Growth moves are only offered to a team that carries enough dependencies for
# the move to mean something: a split needs two to share between the new owners,
# and adding an owner needs one to hand over.
_MIN_COUPLING_TO_SPLIT: int = 2
_MIN_COUPLING_TO_ADD_OWNER: int = 1

# The largest section scored and valuated live. With the precomputed coupling
# index a section down to a whole division (a few hundred teams) scores in under
# a second on its worker thread. Valuating every candidate move still repeats the
# evaluation, so a whole group or company (thousands of teams) stays too heavy to
# score live; above this a scope is an overview to drill into rather than played.
MAX_PLAYABLE_TEAMS: int = 500


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
    # Only the frame's own edges yield moves here: a unit-level dependency
    # is enumerated in the aggregate frame where its endpoints are nodes.
    internal = org.internal_dependencies()
    if internal:
        moves.append(Move(MoveKind.STABILISE_INTERFACES))
    for dep in internal:
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
        self._past: list[OrgState] = []
        self._focus_id: str | None = None

    @property
    def org(self) -> OrgState:
        return self._org

    @property
    def simulator(self) -> Simulator:
        return self._simulator

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
        return len(self._active_org().teams) <= MAX_PLAYABLE_TEAMS

    def candidate_valuations(self) -> tuple[MoveValuation, ...]:
        active = self._active_org()
        if len(active.teams) > MAX_PLAYABLE_TEAMS:
            return ()
        moves = enumerate_moves(active)
        if self._focus_id is not None and child_domains(self._org, self._focus_id):
            moves = tuple(m for m in moves if m.kind in AGGREGATE_MOVE_KINDS)
        return self._simulator.valuate_moves(active, moves)

    def play(self, move: Move) -> None:
        # Apply before snapshotting so a move that cannot apply leaves the
        # session untouched (no orphaned undo snapshot). Store the translated
        # move so the history replays cleanly from the start org; a focused
        # move's raw target can be a domain rather than a real team.
        real = translate_focused_move(self._org, self._focus_id, move)
        new_org = apply_move(self._org, real)
        self._past.append(self._org)
        self._org = new_org
        self._history.append(real)

    @property
    def can_take_back(self) -> bool:
        """Whether there is a move played in this session to undo."""
        return bool(self._past)

    def take_back(self) -> None:
        """Undo the last move played this session, restoring the prior org.

        Each play snapshots the org it replaced, so repeated calls walk the
        position back to where the session started. A session restored from a
        saved game carries no snapshots, so its pre-load moves are not undone.
        """
        if not self._past:
            return
        self._org = self._past.pop()
        self._history.pop()

    def try_play(self, move: Move) -> bool:
        """Play a move if it applies to the current org; report whether it did.

        The guide offers moves from projected future positions, so a later move
        can target a team an earlier move would create. Applying it now would
        fail, so this attempts the pure transform first and commits only when it
        succeeds, leaving the session unchanged otherwise.
        """
        real = translate_focused_move(self._org, self._focus_id, move)
        try:
            new_org = apply_move(self._org, real)
        except FulcrumError:
            return False
        self._past.append(self._org)
        self._org = new_org
        self._history.append(real)
        return True

    def preview(self, move: Move) -> OrgState:
        real = translate_focused_move(self._org, self._focus_id, move)
        return apply_move(self._org, real)
