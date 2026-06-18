"""Tests for the deterministic simulator."""

from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Dependency, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind
from fulcrum.domain.simulation import MoveClassification


def _org():
    return OrgState(
        teams=(
            Team("a", "A", False, 0.5),
            Team("b", "B", False, 0.5),
            Team("c", "C", True, 0.2),
        ),
        dependencies=(
            Dependency("a", "b", 5),
            Dependency("b", "c", 5),
            Dependency("a", "c", 5),
        ),
        workload=7,
    )


def test_score_and_valuate_move():
    sim = DeterministicSimulator()
    org = _org()
    assert 0.0 <= sim.score(org).value <= 100.0
    valuation = sim.valuate_move(org, Move(MoveKind.COLLAPSE_BOUNDARY, ("a", "b")))
    assert valuation.delta > 0
    assert valuation.classification in (
        MoveClassification.GOOD,
        MoveClassification.GREAT,
    )


def test_valuate_moves_returns_one_per_move():
    sim = DeterministicSimulator()
    valuations = sim.valuate_moves(_org(), (Move(MoveKind.STABILISE_INTERFACES),))
    assert len(valuations) == 1
