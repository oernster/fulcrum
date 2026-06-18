"""Tests for the structural evaluation model."""

import pytest

from fulcrum.domain.errors import InvalidOrgStateError
from fulcrum.domain.models import Dependency, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind, apply_move
from fulcrum.domain.simulation import (
    DEFAULT_PARAMETERS,
    ClassificationThresholds,
    MoveClassification,
    SimulationParameters,
    classify_delta,
    coupling_of,
    depended_upon,
    evaluate,
    incoming_delay,
    influence_load,
    influence_without_authority,
    team_arrivals,
    team_capacity,
    team_imbalance,
)


def _t(team_id, authority=True, skew=0.0):
    return Team(
        id=team_id,
        name=team_id.upper(),
        has_local_authority=authority,
        incentive_skew=skew,
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"base_capacity": 0.0},
        {"authority_penalty": 0.0},
        {"authority_penalty": 1.5},
        {"latency_weight": 0.5, "escalation_weight": 0.5, "rework_weight": 0.5},
        {"max_score": 0.0},
        {"cognitive_load_weight": -0.1},
        {"ideal_team_size": 0},
        {"influence_weight": -0.1},
        {"influence_tolerance": -1},
    ],
)
def test_parameters_invalid(kwargs):
    with pytest.raises(InvalidOrgStateError):
        SimulationParameters(**kwargs)


def test_parameters_valid_default():
    assert DEFAULT_PARAMETERS.max_score == 100.0


def test_structural_helpers():
    org = OrgState(
        teams=(_t("a"), _t("b")),
        dependencies=(Dependency("a", "b", 4),),
        workload=5,
    )
    assert coupling_of(org, "a") == 1
    assert incoming_delay(org, "b") == 4.0
    assert incoming_delay(org, "a") == 0.0
    with_authority = team_capacity(org, org.team("a"))
    without_authority = team_capacity(org, _t("x", authority=False))
    assert with_authority > without_authority
    assert team_arrivals(org, org.team("b")) > org.workload


def test_imbalance_floors_at_zero_for_healthy_team():
    org = OrgState(teams=(_t("a", authority=True),), workload=1)
    assert team_imbalance(org, org.team("a")) == 0.0


def test_capacity_falls_once_team_size_exceeds_the_band():
    org = OrgState(
        teams=(
            Team("a", "A", True, 0.0, size=1),
            Team("big", "Big", True, 0.0, size=6),
        ),
        workload=1,
    )
    assert team_capacity(org, org.team("big")) < team_capacity(org, org.team("a"))


def test_collapsing_past_the_band_lowers_the_score():
    org = OrgState(
        teams=(
            Team("a", "A", True, 0.0, size=3),
            Team("b", "B", True, 0.0, size=3),
        ),
        dependencies=(Dependency("a", "b", 0),),
        workload=6,
    )
    before = evaluate(org).value
    after = evaluate(
        apply_move(org, Move(MoveKind.COLLAPSE_BOUNDARY, ("a", "b")))
    ).value
    assert after < before


def test_influence_without_authority_penalises_an_authority_less_hub():
    org = OrgState(
        teams=(_t("hub", authority=False), _t("a"), _t("b")),
        dependencies=(Dependency("hub", "a", 0), Dependency("hub", "b", 0)),
        workload=1,
    )
    assert depended_upon(org, "hub") == 2
    assert influence_without_authority(org, org.team("hub")) == 1.0
    assert influence_load(org) == 1.0
    penalised = evaluate(org).value
    empowered = apply_move(org, Move(MoveKind.DELEGATE_AUTHORITY, ("hub",)))
    assert influence_load(empowered) == 0.0
    assert evaluate(empowered).value > penalised


def test_influence_is_zero_for_an_empowered_hub():
    org = OrgState(
        teams=(_t("hub", authority=True), _t("a"), _t("b")),
        dependencies=(Dependency("hub", "a", 0), Dependency("hub", "b", 0)),
        workload=1,
    )
    assert influence_without_authority(org, org.team("hub")) == 0.0
    assert influence_load(org) == 0.0


def test_evaluate_bounds_and_ordering():
    healthy = OrgState(teams=(_t("a", True, 0.0), _t("b", True, 0.0)), workload=1)
    broken = OrgState(
        teams=(_t("a", False, 0.9), _t("b", False, 0.9), _t("c", False, 0.9)),
        dependencies=(
            Dependency("a", "b", 8),
            Dependency("b", "c", 8),
            Dependency("a", "c", 8),
        ),
        workload=9,
    )
    high = evaluate(healthy).value
    low = evaluate(broken).value
    assert high == 100.0
    assert 0.0 <= low < high


@pytest.mark.parametrize(
    "delta,expected",
    [
        (20.0, MoveClassification.GREAT),
        (5.0, MoveClassification.GOOD),
        (1.0, MoveClassification.NEUTRAL),
        (-0.5, MoveClassification.BAD),
        (-5.0, MoveClassification.BLUNDER),
    ],
)
def test_classify_delta(delta, expected):
    assert classify_delta(delta) == expected


def test_classify_delta_custom_thresholds():
    thresholds = ClassificationThresholds(
        great_delta=2.0, good_delta=1.0, blunder_delta=-1.0
    )
    assert classify_delta(2.0, thresholds) == MoveClassification.GREAT


def test_move_orderings_are_sane():
    org = OrgState(
        teams=(_t("a", False, 0.5), _t("b", False, 0.5), _t("c", True, 0.2)),
        dependencies=(
            Dependency("a", "b", 5),
            Dependency("b", "c", 5),
            Dependency("a", "c", 5),
        ),
        workload=7,
    )
    base = evaluate(org).value
    collapse = evaluate(apply_move(org, Move(MoveKind.COLLAPSE_BOUNDARY, ("a", "b"))))
    delegate = evaluate(apply_move(org, Move(MoveKind.DELEGATE_AUTHORITY, ("a", "b"))))
    approval = evaluate(apply_move(org, Move(MoveKind.ADD_APPROVAL_LAYER)))
    assert collapse.value > base
    assert delegate.value > base
    assert approval.value < base
    assert classify_delta(collapse.value - base) in (
        MoveClassification.GOOD,
        MoveClassification.GREAT,
    )
    assert classify_delta(approval.value - base) in (
        MoveClassification.BAD,
        MoveClassification.BLUNDER,
    )
