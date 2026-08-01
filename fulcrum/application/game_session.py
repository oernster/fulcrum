"""The game session: current position, move history and scoring.

A session is a mutable coordinator. It owns no rules of its own; it composes the
pure domain (apply_move, signals) with an injected simulator.
"""

from __future__ import annotations

from fulcrum.application.dto import MoveValuation, SessionSnapshot
from fulcrum.application.interfaces import Simulator
from fulcrum.application.move_text import describe_move
from fulcrum.domain.errors import FulcrumError
from fulcrum.domain.hierarchy import (
    AGGREGATE_MOVE_KINDS,
    TOP_LEVEL_FOCUS,
    domain_has_teams,
    focused_suborg,
    has_aggregate_children,
    top_level_section,
    translate_focused_move,
)
from fulcrum.domain.models import OrgState, Team
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
        if org.claims_on(team.id):
            _append_claim_moves(org, team, moves)
        elif not team.has_local_authority:
            moves.append(Move(MoveKind.DELEGATE_AUTHORITY, (team.id,)))
        if team.incentive_skew > 0:
            moves.append(Move(MoveKind.REALIGN_INCENTIVES, (team.id,)))
    # Only the frame's own edges yield moves here: a unit-level dependency
    # is enumerated in the aggregate frame where its endpoints are nodes.
    # Stabilise carries the frame's node ids, so playing it thins exactly
    # the edges this frame prices rather than every dependency in the org.
    internal = org.internal_dependencies()
    if internal:
        moves.append(Move(MoveKind.STABILISE_INTERFACES, tuple(org.team_ids)))
    for dep in internal:
        moves.append(Move(MoveKind.COLLAPSE_BOUNDARY, (dep.upstream, dep.downstream)))
    moves.append(Move(MoveKind.ADD_APPROVAL_LAYER))
    moves.append(Move(MoveKind.IMPOSE_MATRIX_OVERLAY))
    if allow_growth:
        _append_growth_moves(org, moves)
    return tuple(moves)


def _append_claim_moves(org: OrgState, team: Team, moves: list[Move]) -> None:
    """The moves a claimed team opens: resolve the contest, downgrade a claim.

    Any standing claim is contest (the structural owner is already claimant
    one), so a claimed team never gets a plain delegate move: granting
    authority without settling the claims would add a claimant, not remove
    one. Resolution offers every ending: the team takes the class, or a
    claimant does. Downgrade is only offered for modelled claimants; an
    unmodelled label is dealt with by resolving instead.
    """
    claims = org.claims_on(team.id)
    winners = [team.id] + [claim.claimant for claim in claims]
    for winner in winners:
        moves.append(Move(MoveKind.RESOLVE_AUTHORITY, (team.id, winner)))
    known = set(org.team_ids) | {d.id for d in org.domains}
    for claim in claims:
        if claim.claimant in known:
            moves.append(Move(MoveKind.DOWNGRADE_CLAIM, (claim.claimant, team.id)))


def record_positions(
    initial: OrgState, history: tuple[Move, ...]
) -> tuple[OrgState, ...]:
    """Every position the record passed through: the start, then one per move.

    The stored history carries translated real moves, so replaying from the
    starting organisation reproduces each position exactly; position i is
    the org before history[i] and position i + 1 the org after it.
    """
    positions = [initial]
    for move in history:
        positions.append(apply_move(positions[-1], move))
    return tuple(positions)


def _append_growth_moves(org: OrgState, moves: list[Move]) -> None:
    for team in org.teams:
        coupling = coupling_of(org, team.id)
        if coupling >= _MIN_COUPLING_TO_SPLIT:
            moves.append(Move(MoveKind.SPLIT_TEAM, (team.id,)))
        if coupling >= _MIN_COUPLING_TO_ADD_OWNER:
            moves.append(Move(MoveKind.ADD_TEAM, (team.id,)))


def scope_moves(
    org: OrgState, focus_id: str | None, active: OrgState
) -> tuple[Move, ...]:
    """The candidate moves for a scope.

    At the top-level frame there are none: every move is made by an authority
    above its target and nothing sits above the top level to make one. At any
    other aggregate scope, only the kinds that translate cleanly down to the
    real teams are offered. This is the single rule for what a scope offers,
    shared by the session and the off-thread analysis so they cannot drift.
    """
    if focus_id == TOP_LEVEL_FOCUS:
        return ()
    moves = enumerate_moves(active)
    if focus_id is not None and has_aggregate_children(org, focus_id):
        return tuple(m for m in moves if m.kind in AGGREGATE_MOVE_KINDS)
    return moves


class GameSession:
    """Coordinates an org state with an injected simulator and persistence."""

    def __init__(self, org: OrgState, simulator: Simulator) -> None:
        self._org = org
        self._initial_org = org
        self._simulator = simulator
        self._history: list[Move] = []
        self._past: list[OrgState] = []
        self._focus_id: str | None = None
        self._prior_count = 0

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
    def prior_history_count(self) -> int:
        """How many history moves came from earlier runs (or an import)."""
        return self._prior_count

    def mark_history_as_prior(self) -> None:
        """Everything played so far becomes the record of earlier runs."""
        self._prior_count = len(self._history)

    def snapshot(self) -> SessionSnapshot:
        """The session as persisted: start org, every move and the result."""
        return SessionSnapshot(self._initial_org, self.history, self._org)

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
        permanent. TOP_LEVEL_FOCUS plays the top level itself as a frame of
        rolled root units. Passing None, a domain with no teams or the top
        level of a flat org returns to the whole org.
        """
        if domain_id == TOP_LEVEL_FOCUS:
            if not self._org.domains:
                domain_id = None
        elif domain_id is not None and not domain_has_teams(self._org, domain_id):
            domain_id = None
        self._focus_id = domain_id

    def _active_org(self) -> OrgState:
        """The org currently being scored: the focused section, or the whole."""
        if self._focus_id is None:
            return self._org
        if self._focus_id == TOP_LEVEL_FOCUS:
            return top_level_section(self._org)
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
        return self._simulator.valuate_moves(
            active, scope_moves(self._org, self._focus_id, active)
        )

    def _frame_label(self, move: Move, org: OrgState) -> str:
        """The text the move was played under, in its frame's own terms.

        History outlives the position it was played in (it persists across
        runs and a collapse renames its targets), so the description is
        captured at play time. It is the SAME text the player clicked: a
        top-level delegate reads as its unit, never as the list of real
        teams the translation expands it to.
        """
        return move.label or describe_move(org, move)

    def _org_for_frame(self, frame_id: str | None) -> OrgState:
        """The org a frame shows, for naming a move in the frame's terms.

        A synthetic direct-teams frame translates as a pass-through (its
        moves already target real teams), so it names against the real org.
        """
        if frame_id == TOP_LEVEL_FOCUS:
            return top_level_section(self._org)
        if frame_id is not None and domain_has_teams(self._org, frame_id):
            return focused_suborg(self._org, frame_id)
        return self._org

    def play(self, move: Move) -> None:
        # Apply before snapshotting so a move that cannot apply leaves the
        # session untouched (no orphaned undo snapshot). Store the translated
        # move so the history replays cleanly from the start org; a focused
        # move's raw target can be a domain rather than a real team. The
        # label is the frame's own text, captured before translation.
        label = self._frame_label(move, self._active_org())
        real = translate_focused_move(self._org, self._focus_id, move)
        new_org = apply_move(self._org, real)
        self._past.append(self._org)
        self._org = new_org
        self._history.append(Move(real.kind, real.targets, label))

    @property
    def can_take_back(self) -> bool:
        """Whether there is a move played in this session to undo."""
        return bool(self._past)

    def take_back(self) -> None:
        """Undo the last move played, restoring the prior org.

        Each play snapshots the org it replaced and a restored session is
        rebuilt by replay, so repeated calls walk the position back through
        earlier runs too, all the way to the original organisation. Undoing
        into the record rewrites it: an undone historic move is no longer
        part of any run, so the prior mark clamps down with the history.
        """
        if not self._past:
            return
        self._org = self._past.pop()
        self._history.pop()
        self._prior_count = min(self._prior_count, len(self._history))

    def try_play(self, move: Move) -> bool:
        """Play a move if it applies to the current org; report whether it did.

        The guide offers moves from projected future positions, so a later move
        can target a team an earlier move would create. Applying it now would
        fail, so this attempts the pure transform first and commits only when it
        succeeds, leaving the session unchanged otherwise.
        """
        return self.try_play_in_frame(move, self._focus_id)

    def try_play_in_frame(self, move: Move, frame_id: str | None) -> bool:
        """try_play, but translated against an explicit frame.

        The hierarchy guide plays moves from frames other than the session's
        current focus (a drilled unit's row, the top-level row), so the
        translation must follow the row's frame rather than whatever the
        board happens to be focused on.
        """
        real = translate_focused_move(self._org, frame_id, move)
        try:
            new_org = apply_move(self._org, real)
        except FulcrumError:
            return False
        # Label only once the move is known to apply, in the frame's own
        # terms; a move whose names outrun the frame (a pass-through onto
        # real teams) falls back to naming the translated act.
        try:
            label = self._frame_label(move, self._org_for_frame(frame_id))
        except FulcrumError:
            label = self._frame_label(real, self._org)
        self._past.append(self._org)
        self._org = new_org
        self._history.append(Move(real.kind, real.targets, label))
        return True

    def preview(self, move: Move) -> OrgState:
        real = translate_focused_move(self._org, self._focus_id, move)
        return apply_move(self._org, real)


def restore_session(snapshot: SessionSnapshot, simulator: Simulator) -> GameSession:
    """Rebuild a persisted session by replaying its moves from the start.

    The replay refills the undo stack, so taking a move back works across
    runs. The replayed moves become the prior record (they belong to earlier
    runs). A snapshot whose moves no longer replay (say the file was edited)
    falls back to its stored current org with an empty history, which is
    what the pre-history autosave restored.
    """
    session = GameSession(snapshot.initial_org, simulator)
    for move in snapshot.moves:
        try:
            session.play(move)
        except FulcrumError:
            return GameSession(snapshot.org, simulator)
    session.mark_history_as_prior()
    return session
