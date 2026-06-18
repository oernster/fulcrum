"""Tests for procedural level generation and its solvability guarantee."""

from random import Random

from fulcrum.application.level_generator import generate_level, has_great_move
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Origin, OrgState, Team

_SEED_COUNT = 12


def test_generate_level_is_valid_and_solvable():
    for seed in range(_SEED_COUNT):
        org = generate_level(Random(seed))
        assert isinstance(org, OrgState)
        assert org.origin == Origin.GENERATED
        assert has_great_move(org)


def test_has_great_move_false_for_healthy_org():
    healthy = OrgState(
        teams=(Team("a", "A", True, 0.0), Team("b", "B", True, 0.0)),
        workload=1,
    )
    assert has_great_move(healthy, DeterministicSimulator()) is False
