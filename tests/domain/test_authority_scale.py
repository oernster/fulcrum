"""Conformance suite for the prince band: scale-dependent authority pricing.

Machiavelli holds both positions and the model must encode their union: The
Prince (concentrated authority governs the small state well) and the
Discourses (the durable large state is a republic). Each test pins one
conformance claim, so the scale dependency is structural and checkable
rather than a preference asserted uniformly:

  C1  A founder-autocrat scores well at or below the Dunbar horizon.
  C2  The identical structure scores badly above the band.
  C3  The concentration penalty is monotone in scale, structure fixed.
  C4  A full republic under a common roof is scale-invariant: the band
      prices concentration, never distribution with its interfaces owned.
  C5  The republic preference widens monotonically with scale.
  C6  The penalty saturates at the survivor ceiling: rare princes survive
      at any size, so scale grades the penalty and never prohibits.
  C7  The factor is continuous at both band edges.
  C8  Contest is never forgiven: full price below the horizon and strictly
      worse than clean escalation at every scale, deepening above the band.
  C9  Delegating authority (republicanising) is worth more the larger the
      organisation: the same move reads bigger at scale.
  C10 A Dunbar-sized pocket inside a large organisation may stay princely
      in its own frame while the large frames demand a republic.
Claims C11 to C14 (escalation loads the centre, escalation priced at its
resolution distance, fragmentation priced under no roof, influence priced
proportionally), the conformance half of the adversarial repairs, live in
test_resolution_conformance.py.
"""

from itertools import pairwise

import pytest

from fulcrum.domain.errors import InvalidOrgStateError
from fulcrum.domain.hierarchy import (
    focused_suborg,
    top_level_section,
    total_headcount,
)
from fulcrum.domain.models import AuthorityClaim, Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind, apply_move
from fulcrum.domain.simulation import (
    DEFAULT_PARAMETERS,
    MoveClassification,
    SimulationParameters,
    classify_delta,
    contest_scale_factor,
    evaluate,
    frame_headcount,
    prince_scale_factor,
    scaled_authority_penalty,
    scaled_contested_penalty,
    team_capacity,
)

_PARAMS = DEFAULT_PARAMETERS

# The autocrat fixture has one authoritative centre and this many teams
# escalating to it; per-team headcount moves the total across the band while
# the structure stays fixed.
_SUBORDINATES = 5
_EDICT_DELAY = 2
_WORKLOAD = 4

# Per-team headcounts that place the six-team fixture below the horizon, at
# it, inside the band, just above it and far beyond the ceiling onset.
_LADDER = (1, 8, 25, 28, 30, 33, 100, 1_000, 10_000, 100_000)
_SMALL = 8
_LARGE = 1_000
_SATURATED = (10_000, 100_000)

# Conformance bars, set well clear of the measured values (84.8 and 35.7
# with the default coefficients, the founder carrying its five teams' shed
# escalation load) so the claims survive gentle recalibration while a
# regression to flat pricing still fails both.
_SMALL_PRINCE_FLOOR = 80.0
_LARGE_PRINCE_CEILING = 45.0


def _autocracy(per_team: int, authority_everywhere: bool = False) -> OrgState:
    """A founder-autocrat: every team escalates to one authoritative centre.

    Both shapes live under a common roof (the org itself as a domain): the
    autocracy resolves through the founder either way, and the republic's
    sovereign interfaces are owned by the roof, its senate, so the fixtures
    compare concentration against distribution rather than against
    fragmentation (which test_resolution_conformance.py prices on its own).
    """
    teams = [Team("founder", "Founder", True, domain_id="org", headcount=per_team)]
    for i in range(_SUBORDINATES):
        teams.append(
            Team(
                f"t{i}",
                f"T{i}",
                authority_everywhere,
                domain_id="org",
                headcount=per_team,
            )
        )
    deps = tuple(
        Dependency("founder", f"t{i}", _EDICT_DELAY) for i in range(_SUBORDINATES)
    )
    return OrgState(
        teams=tuple(teams),
        dependencies=deps,
        workload=_WORKLOAD,
        domains=(Domain("org", "Org"),),
    )


def _republic(per_team: int) -> OrgState:
    """The same shape with authority distributed to every team."""
    return _autocracy(per_team, authority_everywhere=True)


def test_c1_founder_autocrat_scores_well_at_dunbar_scale():
    for per_team in (1, _SMALL, 25):
        org = _autocracy(per_team)
        assert frame_headcount(org) <= _PARAMS.dunbar_headcount
        assert evaluate(org).value >= _SMALL_PRINCE_FLOOR


def test_c2_the_same_structure_scores_badly_above_the_band():
    small = evaluate(_autocracy(_SMALL)).value
    large = evaluate(_autocracy(_LARGE)).value
    assert frame_headcount(_autocracy(_LARGE)) > _PARAMS.prince_band_upper
    assert large < _LARGE_PRINCE_CEILING < _SMALL_PRINCE_FLOOR <= small


def test_c3_concentration_penalty_is_monotone_in_scale():
    scores = [evaluate(_autocracy(per_team)).value for per_team in _LADDER]
    assert all(earlier >= later for earlier, later in pairwise(scores))
    # Strictly falling across the band and beyond it, not merely flat.
    assert scores[0] > scores[-1]


def test_c4_a_full_republic_is_scale_invariant():
    baseline = evaluate(_republic(_SMALL)).value
    for per_team in _LADDER:
        assert evaluate(_republic(per_team)).value == baseline


def test_c5_the_republic_preference_widens_with_scale():
    gaps = [
        evaluate(_republic(per_team)).value - evaluate(_autocracy(per_team)).value
        for per_team in _LADDER
    ]
    assert all(gap > 0 for gap in gaps)
    assert all(earlier <= later for earlier, later in pairwise(gaps))
    assert gaps[0] < gaps[-1]


def test_c6_the_penalty_saturates_at_the_survivor_ceiling():
    first, second = (evaluate(_autocracy(p)).value for p in _SATURATED)
    assert first == second
    assert first > 0.0
    huge = _SATURATED[-1] * (_SUBORDINATES + 1)
    assert prince_scale_factor(huge, _PARAMS) == _PARAMS.prince_survivor_ceiling


def test_c7_the_factor_is_continuous_at_both_band_edges():
    lower, upper = _PARAMS.dunbar_headcount, _PARAMS.prince_band_upper
    attenuation = _PARAMS.prince_attenuation
    assert prince_scale_factor(lower, _PARAMS) == attenuation
    assert prince_scale_factor(upper, _PARAMS) == 1.0
    midband = (lower + upper) // 2
    expected_mid = attenuation + (1.0 - attenuation) * (midband - lower) / (
        upper - lower
    )
    assert prince_scale_factor(midband, _PARAMS) == pytest.approx(expected_mid)
    ladder = (1, lower, midband, upper, upper * 10, upper * 1_000)
    factors = [prince_scale_factor(h, _PARAMS) for h in ladder]
    assert all(earlier <= later for earlier, later in pairwise(factors))
    # Parity with the flat model at the band's top edge.
    assert scaled_authority_penalty(_PARAMS, 1.0) == pytest.approx(
        _PARAMS.authority_penalty
    )


def test_c8_contest_is_never_forgiven_below_the_horizon():
    clean = _autocracy(_SMALL)
    contested = OrgState(
        teams=clean.teams,
        dependencies=clean.dependencies,
        workload=clean.workload,
        domains=clean.domains,
        claims=(AuthorityClaim("chapter", "t0"),),
    )
    assert evaluate(contested).value < evaluate(clean).value
    factor = prince_scale_factor(frame_headcount(clean), _PARAMS)
    contested_team = contested.team("t0")
    clean_team = clean.team("t0")
    assert team_capacity(contested, contested_team, _PARAMS) < team_capacity(
        clean, clean_team, _PARAMS
    )
    # Attenuation never reaches contest; amplification does.
    assert contest_scale_factor(factor) == 1.0
    assert contest_scale_factor(_PARAMS.prince_survivor_ceiling) == (
        _PARAMS.prince_survivor_ceiling
    )
    # Below the band contest costs its full flat price; above it the price
    # deepens in proportion to the scaled escalation price, so a contested
    # team's capacity sits strictly below an escalating team's at every
    # scale. The equality regime the min() clamp used to allow is pinned
    # out: this is the repair for the contest-gets-relatively-cheaper
    # finding of the adversarial review.
    assert scaled_contested_penalty(_PARAMS, _PARAMS.prince_attenuation) == (
        _PARAMS.contested_penalty
    )
    ceiling = _PARAMS.prince_survivor_ceiling
    deepened = scaled_contested_penalty(_PARAMS, ceiling)
    assert deepened < scaled_authority_penalty(_PARAMS, ceiling)
    assert deepened == pytest.approx(
        scaled_authority_penalty(_PARAMS, ceiling)
        * _PARAMS.contested_penalty
        / _PARAMS.authority_penalty
    )
    for factor_point in (0.3, 1.0, 1.3, ceiling):
        assert scaled_contested_penalty(_PARAMS, factor_point) < (
            scaled_authority_penalty(_PARAMS, factor_point)
        )


def test_c9_delegation_reads_larger_the_bigger_the_organisation():
    targets = tuple(f"t{i}" for i in range(_SUBORDINATES))
    move = Move(MoveKind.DELEGATE_AUTHORITY, targets)
    deltas = []
    for per_team in _LADDER:
        org = _autocracy(per_team)
        before = evaluate(org).value
        deltas.append(evaluate(apply_move(org, move)).value - before)
    assert all(earlier <= later for earlier, later in pairwise(deltas))
    assert classify_delta(deltas[-1]) == MoveClassification.GREAT
    # Small-scale delegation may itself read great now: it relieves the
    # founder's shed queue (C11), a real gain at any size. The scale claim
    # is strict growth, so the same move is worth more the larger the org.
    assert deltas[-1] > deltas[0]


def test_c10_a_dunbar_pocket_inside_a_large_org_may_stay_princely():
    pocket_teams = tuple(
        Team(
            f"p{i}",
            f"P{i}",
            i == 0,
            domain_id="pocket",
            headcount=_SMALL,
        )
        for i in range(_SUBORDINATES)
    )
    mass_teams = tuple(
        Team(f"m{i}", f"M{i}", True, domain_id="mass", headcount=10_000)
        for i in range(4)
    )
    org = OrgState(
        teams=pocket_teams + mass_teams,
        workload=1,
        domains=(Domain("pocket", "Pocket"), Domain("mass", "Mass")),
    )
    pocket = focused_suborg(org, "pocket")
    assert frame_headcount(pocket) == _SMALL * _SUBORDINATES
    pocket_factor = prince_scale_factor(frame_headcount(pocket), _PARAMS)
    assert pocket_factor == _PARAMS.prince_attenuation
    whole_factor = prince_scale_factor(frame_headcount(org), _PARAMS)
    assert whole_factor > 1.0
    # The rolled top-level frame carries the real population, so the large
    # frame is priced at the whole organisation's scale.
    top = top_level_section(org)
    assert frame_headcount(top) == total_headcount(org)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dunbar_headcount": 0},
        {"prince_band_upper": 150},
        {"prince_attenuation": 0.0},
        {"prince_attenuation": 1.5},
        {"prince_amplification": -0.1},
        {"prince_survivor_ceiling": 0.9},
        {"prince_survivor_ceiling": 2.0},
        {"escalation_load_share": -0.1},
        {"escalation_load_share": 1.5},
        {"unowned_interface_weight": -0.1},
    ],
)
def test_prince_band_parameters_invalid(kwargs):
    with pytest.raises(InvalidOrgStateError):
        SimulationParameters(**kwargs)


def test_prince_band_defaults_are_the_machiavelli_reading():
    assert _PARAMS.dunbar_headcount == 150
    assert _PARAMS.prince_band_upper == 200
    assert 0.0 < _PARAMS.prince_attenuation < 1.0
    assert _PARAMS.prince_amplification > 0.0
    assert _PARAMS.prince_survivor_ceiling * (1.0 - _PARAMS.authority_penalty) < 1.0
