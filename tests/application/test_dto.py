"""Tests for the application data-transfer objects."""

import pytest

from fulcrum.application.dto import MoveValuation
from fulcrum.domain.moves import Move, MoveKind
from fulcrum.domain.simulation import MoveClassification


def test_move_valuation_delta():
    valuation = MoveValuation(
        move=Move(MoveKind.STABILISE_INTERFACES),
        score_before=40.0,
        score_after=52.5,
        classification=MoveClassification.GREAT,
    )
    assert valuation.delta == pytest.approx(12.5)
