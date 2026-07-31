"""Conformance suite for the prince band: scale-dependent authority pricing.

Machiavelli holds both positions and the model must encode their union: The
Prince (concentrated authority governs the small state well) and the
Discourses (the durable large state is a republic). Each test pins one
conformance claim, so the scale dependency is structural and checkable
rather than a preference asserted uniformly:

  C1  A founder-autocrat scores well at or below the Dunbar horizon.
  C2  The identical structure scores badly above the band.
  C3  The concentration penalty is monotone in scale, structure fixed.
  C4  A full republic's score is scale-invariant: the band prices
      concentration only.
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
  C11 Escalation loads the centre: the resolving authority's queue grows
      with the number of teams escalating through it, so a saturated
      centre prices itself however small the organisation is. The shed
      load is never attenuated by the band (friction is forgiven at small
      scale, bandwidth is not).
  C12 Escalation is priced at its resolution distance: a team whose
      authority sits within its own Dunbar-sized unit is priced at that
      unit's population however large the whole organisation is, so an
      organisation of empowered pockets reads the same at any unit count
      while stripping the pocket leads collapses it.
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
    scale_context,
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
    """A founder-autocrat: every team escalates to one authoritative centre."""
    teams = [Team("founder", "Founder", True, headcount=per_team)]
    for i in range(_SUBORDINATES):
        teams.append(Team(f"t{i}", f"T{i}", authority_everywhere, headcount=per_team))
    deps = tuple(
        Dependency("founder", f"t{i}", _EDICT_DELAY) for i in range(_SUBORDINATES)
    )
    return OrgState(teams=tuple(teams), dependencies=deps, workload=_WORKLOAD)


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


def _span_autocracy(n_subordinates: int, total_people: int = 148) -> OrgState:
    """A centre with a widening span at a fixed sub-Dunbar population."""
    per = max(1, total_people // (n_subordinates + 1))
    teams = [Team("founder", "Founder", True, headcount=per)]
    teams += [
        Team(f"t{i}", f"T{i}", False, headcount=per) for i in range(n_subordinates)
    ]
    return OrgState(teams=tuple(teams), workload=_WORKLOAD)


def test_c11_escalation_loads_the_centre():
    spans = (2, 5, 10, 20, 30)
    orgs = [_span_autocracy(n) for n in spans]
    inflows = [scale_context(org, _PARAMS).inflow["founder"] for org in orgs]
    assert all(earlier < later for earlier, later in pairwise(inflows))
    expected = _PARAMS.escalation_load_share * _WORKLOAD * spans[-1]
    assert inflows[-1] == pytest.approx(expected)
    scores = [evaluate(org).value for org in orgs]
    assert all(earlier > later for earlier, later in pairwise(scores))
    # A republic sheds nothing: no team escalates, so no queue forms.
    republic = OrgState(
        teams=tuple(t.with_authority(True) for t in orgs[-1].teams),
        workload=_WORKLOAD,
    )
    assert all(
        value == 0.0 for value in scale_context(republic, _PARAMS).inflow.values()
    )


def _pocket_org(n_units: int, leads_have_authority: bool) -> OrgState:
    """Dunbar-sized units, each with a lead its four teams escalate to."""
    teams: list[Team] = []
    domains: list[Domain] = []
    deps: list[Dependency] = []
    for unit in range(n_units):
        uid = f"u{unit}"
        domains.append(Domain(uid, f"Unit {unit}"))
        lead_id = f"{uid}_lead"
        teams.append(
            Team(
                lead_id,
                f"Lead {unit}",
                leads_have_authority,
                domain_id=uid,
                headcount=10,
            )
        )
        for i in range(4):
            team_id = f"{uid}_t{i}"
            teams.append(
                Team(team_id, f"T{unit}.{i}", False, domain_id=uid, headcount=10)
            )
            deps.append(Dependency(lead_id, team_id, 1))
    return OrgState(
        teams=tuple(teams),
        dependencies=tuple(deps),
        workload=3,
        domains=tuple(domains),
    )


def test_c12_escalation_is_priced_at_its_resolution_distance():
    small = _pocket_org(4, leads_have_authority=True)
    large = _pocket_org(100, leads_have_authority=True)
    # Every escalation resolves within a 50-person unit, so the headline
    # does not change with the number of units: the whole-org frame no
    # longer prices a desk-distance escalation at conglomerate scale.
    assert evaluate(large).value == pytest.approx(evaluate(small).value)
    context = scale_context(large, _PARAMS)
    assert context.factors["u0_t0"] == _PARAMS.prince_attenuation
    assert context.frame_factor > 1.0
    # The shed load stays inside the unit, on its own lead.
    per_lead = _PARAMS.escalation_load_share * large.workload * 4
    assert context.inflow["u0_lead"] == pytest.approx(per_lead)
    assert context.inflow["u1_t0"] == 0.0
    # Strip the leads and nothing resolves below the summit: the same
    # organisation collapses, which is the difference between a federation
    # of principalities and an org where nobody can decide.
    headless = _pocket_org(100, leads_have_authority=False)
    headless_context = scale_context(headless, _PARAMS)
    assert headless_context.factors["u0_t0"] == headless_context.frame_factor
    assert all(value == 0.0 for value in headless_context.inflow.values())
    assert evaluate(headless).value < evaluate(large).value / 2
