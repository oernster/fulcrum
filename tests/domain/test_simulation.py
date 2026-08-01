"""Tests for the structural evaluation model."""

import pytest

from fulcrum.domain.errors import InvalidOrgStateError
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind, apply_move
from fulcrum.domain.simulation import (
    DEFAULT_PARAMETERS,
    ClassificationThresholds,
    MoveClassification,
    SimulationParameters,
    classify_delta,
    coupling_of,
    depended_upon,
    dependency_index,
    evaluate,
    incoming_delay,
    influence_load,
    influence_without_authority,
    team_arrivals,
    team_capacity,
    team_imbalance,
)


def _t(team_id, authority=True, skew=0.0, domain_id=None):
    return Team(
        id=team_id,
        name=team_id.upper(),
        has_local_authority=authority,
        incentive_skew=skew,
        domain_id=domain_id,
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
        {"dependent_demand_weight": -0.1},
        # A dependency line may never cost more than an escalation line.
        {"dependent_demand_weight": 0.3},
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
    # Same uncoupled team either way, so the comparison isolates authority;
    # at this org's tiny scale the gap is attenuated but never zero.
    with_authority = team_capacity(org, _t("x"))
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
    # Roofed, so delegating to the hub compares influence against
    # empowerment rather than creating roofless sovereign interfaces
    # (fragmentation has its own conformance suite).
    roof = (Domain("company", "Company"),)
    org = OrgState(
        teams=(
            _t("hub", authority=False, domain_id="company"),
            _t("a", domain_id="company"),
            _t("b", domain_id="company"),
        ),
        dependencies=(Dependency("hub", "a", 0), Dependency("hub", "b", 0)),
        workload=1,
        domains=roof,
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
    # Roofed under one company so the orderings isolate what they guard
    # (delegation beats escalation, approval layers cost): without a roof,
    # delegating both teams trades escalation for unowned-interface
    # fragmentation while the hub keeps its routed dependent demand, and
    # the delegation sliver legitimately vanishes.
    org = OrgState(
        teams=(
            _t("a", False, 0.5, domain_id="co"),
            _t("b", False, 0.5, domain_id="co"),
            _t("c", True, 0.2, domain_id="co"),
        ),
        dependencies=(
            Dependency("a", "b", 5),
            Dependency("b", "c", 5),
            Dependency("a", "c", 5),
        ),
        workload=7,
        domains=(Domain("co", "Company"),),
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


def test_unit_level_dependencies_never_bind_a_team_frame():
    org = OrgState(
        teams=(_t("a"), _t("b")),
        dependencies=(
            Dependency("a", "b", 3),
            Dependency("d1", "a", 9),
            Dependency("b", "d1", 9),
        ),
        workload=2,
        domains=(Domain("d1", "Platform"),),
    )
    index = dependency_index(org)
    assert index.coupling == {"a": 1, "b": 1}
    assert index.depended_upon == {"a": 1, "b": 0}
    assert index.incoming_delay["b"] == 3.0
    for team_id in ("a", "b"):
        assert coupling_of(org, team_id) == index.coupling[team_id]
        assert depended_upon(org, team_id) == index.depended_upon[team_id]
        assert incoming_delay(org, team_id) == index.incoming_delay[team_id]


def _fan_org(spokes: int, weightless: bool = False) -> OrgState:
    """Thirty-five sovereign teams; the first `spokes` wait on t0."""
    teams = tuple(Team(f"t{i}", f"T{i}", True, 0.0, headcount=5) for i in range(35))
    deps = tuple(Dependency("t0", f"t{i}", 2) for i in range(1, spokes + 1))
    return OrgState(teams=teams, dependencies=deps, workload=2)


def _pairs_org() -> OrgState:
    """The same teams and delays arranged as disjoint pairs."""
    teams = tuple(Team(f"t{i}", f"T{i}", True, 0.0, headcount=5) for i in range(35))
    deps = tuple(Dependency(f"t{i}", f"t{i + 1}", 2) for i in range(1, 34, 2))
    return OrgState(teams=teams, dependencies=deps, workload=2)


def test_dependency_concentration_prices_itself():
    # The falsifiable claim: a hub every team waits on scores clearly below
    # the same sovereign teams in disjoint pairs. Authority concentration
    # already priced itself; this is the same singularity on the dependency
    # channel (Little's law; LatencyLab's serial-queue placement result).
    gap = evaluate(_pairs_org()).value - evaluate(_fan_org(34)).value
    assert gap >= 4.0
    off = SimulationParameters(dependent_demand_weight=0.0)
    old_gap = evaluate(_pairs_org(), off).value - evaluate(_fan_org(34), off).value
    assert old_gap < 2.0


def test_distributed_fan_out_stays_free():
    # A single-dependent upstream absorbs the routed demand within its
    # capacity headroom, so the cost begins where the queue does: the pairs
    # org prices identically with the term on and off.
    off = SimulationParameters(dependent_demand_weight=0.0)
    assert evaluate(_pairs_org()).value == pytest.approx(
        evaluate(_pairs_org(), off).value
    )


def test_hub_cost_grows_with_fan_out():
    scores = [evaluate(_fan_org(n)).value for n in (4, 8, 16, 32)]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] > scores[-1]


def test_dependent_demand_lands_on_the_upstream_queue():
    org = OrgState(
        teams=(_t("hub"), _t("x"), _t("y"), _t("z")),
        dependencies=(
            Dependency("hub", "x", 0),
            Dependency("hub", "y", 0),
            Dependency("hub", "z", 0),
        ),
        workload=2,
    )
    p = DEFAULT_PARAMETERS
    expected = org.workload * (1.0 + p.dependent_demand_weight * 3)
    assert team_arrivals(org, org.team("hub"), p) == pytest.approx(expected)
    # A downstream team carries no routed demand, only its own workload.
    assert team_arrivals(org, org.team("x"), p) == pytest.approx(org.workload)
