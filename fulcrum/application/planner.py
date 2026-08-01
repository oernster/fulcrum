"""Improvement planner: a greedy guide from an org toward a stronger one.

This is the engine behind the Guide (the optional 'cheat' view). From the
current position it repeatedly takes the strongest improving move and returns
the chain with the running score, the way a chess engine shows its best line.
With allow_growth the planner may also grow the org (splitting a team or adding
an owner); left off, it plans at a fixed size, the 'do not grow' path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fulcrum.application.game_session import enumerate_moves
from fulcrum.application.interfaces import Simulator
from fulcrum.application.move_text import describe_move
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, MoveKind, apply_move
from fulcrum.domain.simulation import MoveClassification

_DEFAULT_MAX_STEPS = 12
_DEFAULT_MIN_GAIN = 0.5

# With a progress callback, candidates are valuated in chunks this size so
# long steps report life mid-step. Each chunk re-scores the base position
# once, so the chunk is sized to keep that overhead a few percent while a
# whole-org growth step (hundreds of half-second valuations) still ticks
# every few seconds.
_PROGRESS_CHUNK = 16


@dataclass(frozen=True, slots=True)
class GuideStep:
    """One move in the guide, with the org and score it acts on and produces."""

    move: Move
    classification: MoveClassification
    score_after: float
    org_before: OrgState
    score_before: float


@dataclass(frozen=True, slots=True)
class Guide:
    """An ordered chain of improving moves from a start score to a final one."""

    start_score: float
    final_score: float
    steps: tuple[GuideStep, ...]


@dataclass(frozen=True, slots=True)
class ImprovementPlanner:
    """Plans a greedy improvement chain over an injected simulator."""

    simulator: Simulator
    max_steps: int = _DEFAULT_MAX_STEPS
    min_gain: float = _DEFAULT_MIN_GAIN
    allow_growth: bool = False

    def plan(
        self,
        org: OrgState,
        allowed_kinds: tuple[MoveKind, ...] | None = None,
        move_filter: Callable[[Move], bool] | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> Guide:
        """Plan the greedy line; progress, if given, receives the number of
        candidates valuated after each chunk, so a caller can keep a bar
        alive through a step that valuates hundreds of moves."""
        start = self.simulator.score(org).value
        current = org
        current_score = start
        steps: list[GuideStep] = []
        played: set[tuple[MoveKind, tuple[str, ...]]] = set()
        for _ in range(self.max_steps):
            moves = enumerate_moves(current, allow_growth=self.allow_growth)
            if allowed_kinds is not None:
                moves = tuple(m for m in moves if m.kind in allowed_kinds)
            if move_filter is not None:
                moves = tuple(m for m in moves if move_filter(m))
            # Never repeat an identical move within one line: replaying a
            # partial repair (realign, stabilise) converges with diminishing
            # gains, and a guide that names the same move three times reads
            # as noise rather than a plan. Each repair appears once.
            moves = tuple(m for m in moves if (m.kind, m.targets) not in played)
            if not moves:
                break
            best = max(
                self._valuate(current, moves, progress),
                key=lambda valuation: valuation.delta,
            )
            if best.delta < self.min_gain:
                break
            played.add((best.move.kind, best.move.targets))
            label = describe_move(current, best.move)
            before = current
            score_before = current_score
            current = apply_move(current, best.move)
            current_score = best.score_after
            steps.append(
                GuideStep(
                    move=Move(best.move.kind, best.move.targets, label),
                    classification=best.classification,
                    score_after=current_score,
                    org_before=before,
                    score_before=score_before,
                )
            )
        return Guide(start_score=start, final_score=current_score, steps=tuple(steps))

    def _valuate(
        self,
        org: OrgState,
        moves: tuple[Move, ...],
        progress: Callable[[int], None] | None,
    ):
        if progress is None:
            return self.simulator.valuate_moves(org, moves)
        valuations = []
        for at in range(0, len(moves), _PROGRESS_CHUNK):
            chunk = moves[at : at + _PROGRESS_CHUNK]
            valuations.extend(self.simulator.valuate_moves(org, chunk))
            progress(len(chunk))
        return valuations
