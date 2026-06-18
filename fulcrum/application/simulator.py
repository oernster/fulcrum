"""A simulator over the deterministic domain evaluation.

For a generated level the parameters are known, so a single deterministic pass
is exact. The same Protocol seam lets a later implementation sample uncertain
parameters for a user-specified org without changing its callers.
"""

from __future__ import annotations

from dataclasses import dataclass

from fulcrum.application.dto import MoveValuation
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, apply_move
from fulcrum.domain.simulation import (
    DEFAULT_PARAMETERS,
    DEFAULT_THRESHOLDS,
    ClassificationThresholds,
    SimulationParameters,
    StructuralScore,
    classify_delta,
    evaluate,
)


@dataclass(frozen=True, slots=True)
class DeterministicSimulator:
    """Scores org states and valuates moves with the domain model."""

    params: SimulationParameters = DEFAULT_PARAMETERS
    thresholds: ClassificationThresholds = DEFAULT_THRESHOLDS

    def score(self, org: OrgState) -> StructuralScore:
        return evaluate(org, self.params)

    def valuate_move(self, org: OrgState, move: Move) -> MoveValuation:
        before = evaluate(org, self.params).value
        after = evaluate(apply_move(org, move), self.params).value
        return MoveValuation(
            move=move,
            score_before=before,
            score_after=after,
            classification=classify_delta(after - before, self.thresholds),
        )

    def valuate_moves(
        self, org: OrgState, moves: tuple[Move, ...]
    ) -> tuple[MoveValuation, ...]:
        return tuple(self.valuate_move(org, move) for move in moves)
