"""Improvement planner: a greedy guide from an org toward a stronger one.

This is the engine behind the Guide (the optional 'cheat' view). From the
current position it repeatedly takes the strongest improving move and returns
the chain with the running score, the way a chess engine shows its best line.
With allow_growth the planner may also grow the org (splitting a team or adding
an owner); left off, it plans at a fixed size, the 'do not grow' path.
"""

from __future__ import annotations

from dataclasses import dataclass

from fulcrum.application.game_session import enumerate_moves
from fulcrum.application.interfaces import Simulator
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, apply_move
from fulcrum.domain.simulation import MoveClassification

_DEFAULT_MAX_STEPS = 12
_DEFAULT_MIN_GAIN = 0.5


@dataclass(frozen=True, slots=True)
class GuideStep:
    """One move in the guide, with the score that follows it."""

    move: Move
    classification: MoveClassification
    score_after: float


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

    def plan(self, org: OrgState) -> Guide:
        start = self.simulator.score(org).value
        current = org
        current_score = start
        steps: list[GuideStep] = []
        for _ in range(self.max_steps):
            valuations = self.simulator.valuate_moves(
                current, enumerate_moves(current, allow_growth=self.allow_growth)
            )
            best = max(valuations, key=lambda valuation: valuation.delta)
            if best.delta < self.min_gain:
                break
            current = apply_move(current, best.move)
            current_score = best.score_after
            steps.append(
                GuideStep(
                    move=best.move,
                    classification=best.classification,
                    score_after=current_score,
                )
            )
        return Guide(start_score=start, final_score=current_score, steps=tuple(steps))
