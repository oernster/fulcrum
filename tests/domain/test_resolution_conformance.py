"""Conformance suite for resolution neighbourhoods and proportional pricing.

These claims pin the four adversarial repairs, so a regression to any of
the mispricings the review found fails loudly:

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
  C13 Fragmentation is priced under no roof: a dependency between two
      clean sovereigns sharing no enclosing domain has nowhere to take a
      conflict, so a roofless sovereign network is priced with scale while
      the same network under a common roof, and two founders across a
      desk, stay cheap.
  C14 Influence is priced proportionally: one overloaded hub costs a
      large organisation a slice of its score, never half of it, and the
      same hub costs a small organisation relatively more.
  C15 Claims are priced proportionally: a standing claim costs its share
      of the organisation it contests, never a flat tithe on the whole.
  C16 Shed load follows the wiring: a resolving authority receives the
      escalations it actually has dependencies with, so a disconnected
      puppet authority absorbs nothing and cannot launder a saturated
      centre; wiring it in costs coupling on both ends.
  C17 A roof needs an officer: a shared domain owns its sovereigns'
      interfaces only when its subtree holds a clean authority beyond the
      two endpoints, so two sovereigns alone under a nominal roof are
      still unowned.

Claims C1 to C10, the prince band itself, live in test_authority_scale.py.
"""

from itertools import pairwise

import pytest

from fulcrum.domain.models import AuthorityClaim, Dependency, Domain, OrgState, Team
from fulcrum.domain.simulation import DEFAULT_PARAMETERS, evaluate, scale_context

_PARAMS = DEFAULT_PARAMETERS
_WORKLOAD = 4

# Per-team headcounts spanning the band, as in the C1 to C10 ladder.
_LADDER = (1, 8, 25, 30, 100, 1_000, 10_000)

# A roofless pair of founders must stay near-perfect: small republics run
# on direct negotiation. Measured 95.5 with the default coefficients.
_TWO_FOUNDER_FLOOR = 90.0

# One advisory hub in a large healthy organisation costs a proportionate
# slice, never a collapse. Measured 3.4 points with the defaults.
_HUB_COST_CEILING = 6.0


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
    # A lead-to-team edge is never an unowned interface: one endpoint
    # escalates, so the edge already resolves along its line.
    assert all(count == 0 for count in context.unowned.values())
    # Strip the leads and nothing resolves below the summit: the same
    # organisation collapses, which is the difference between a federation
    # of principalities and an org where nobody can decide.
    headless = _pocket_org(100, leads_have_authority=False)
    headless_context = scale_context(headless, _PARAMS)
    assert headless_context.factors["u0_t0"] == headless_context.frame_factor
    assert all(value == 0.0 for value in headless_context.inflow.values())
    assert evaluate(headless).value < evaluate(large).value / 2


def _sovereign_chain(per_team: int, roofed: bool) -> OrgState:
    """Six sovereign teams in a dependency chain, with or without a roof."""
    domain_id = "company" if roofed else None
    teams = tuple(
        Team(f"s{i}", f"S{i}", True, domain_id=domain_id, headcount=per_team)
        for i in range(6)
    )
    deps = tuple(Dependency(f"s{i}", f"s{i + 1}", 0) for i in range(5))
    domains = (Domain("company", "Company"),) if roofed else ()
    return OrgState(teams=teams, dependencies=deps, workload=1, domains=domains)


def test_c13_fragmentation_is_priced_under_no_roof():
    context = scale_context(_sovereign_chain(8, roofed=False), _PARAMS)
    assert context.unowned["s0"] == 1
    assert context.unowned["s1"] == 2
    roofless = [
        evaluate(_sovereign_chain(per_team, roofed=False)).value for per_team in _LADDER
    ]
    assert all(earlier >= later for earlier, later in pairwise(roofless))
    assert roofless[0] > roofless[-1]
    # Two founders across a desk: sovereignty without institutions is
    # near-free below the horizon, Machiavelli's productive tumults.
    assert roofless[0] >= _TWO_FOUNDER_FLOOR
    # The same network under a common roof has somewhere to take every
    # conflict: no unowned interfaces, no fragmentation price, at any size.
    roofed = [
        evaluate(_sovereign_chain(per_team, roofed=True)).value for per_team in _LADDER
    ]
    assert all(score == roofed[0] for score in roofed)
    assert all(
        count == 0
        for count in scale_context(
            _sovereign_chain(1_000, roofed=True), _PARAMS
        ).unowned.values()
    )
    assert roofed[-1] > roofless[-1]


def _advisory_org(n_healthy: int, with_hub: bool) -> OrgState:
    """A healthy roofed organisation, optionally with one overloaded hub."""
    teams = [
        Team(f"t{i}", f"T{i}", True, domain_id="company", headcount=100)
        for i in range(n_healthy)
    ]
    deps: tuple[Dependency, ...] = ()
    if with_hub:
        teams.append(Team("hub", "Advisory", False, domain_id="company", headcount=8))
        deps = tuple(Dependency("hub", f"t{i}", 1) for i in range(10))
    return OrgState(
        teams=tuple(teams),
        dependencies=deps,
        workload=3,
        domains=(Domain("company", "Company"),),
    )


def test_c14_influence_is_priced_proportionally():
    large_base = evaluate(_advisory_org(50, with_hub=False)).value
    large_cost = large_base - evaluate(_advisory_org(50, with_hub=True)).value
    assert 0.0 < large_cost <= _HUB_COST_CEILING
    # The identical hub weighs relatively more in a smaller organisation.
    small_base = evaluate(_advisory_org(12, with_hub=False)).value
    small_cost = small_base - evaluate(_advisory_org(12, with_hub=True)).value
    assert small_cost > large_cost


def test_c15_claims_are_priced_proportionally():
    """One claim costs a large organisation its share, never a tithe."""
    teams = tuple(
        Team(f"t{i}", f"T{i}", True, domain_id="company", headcount=100)
        for i in range(50)
    )
    roof = (Domain("company", "Company"),)
    base = OrgState(teams=teams, workload=3, domains=roof)
    claimed = OrgState(
        teams=teams,
        workload=3,
        domains=roof,
        claims=(AuthorityClaim("chapter", "t0"),),
    )
    cost = evaluate(base).value - evaluate(claimed).value
    assert 0.0 < cost <= _HUB_COST_CEILING
    # The identical claim weighs relatively more in a small organisation.
    small_teams = tuple(
        Team(f"t{i}", f"T{i}", True, domain_id="company", headcount=100)
        for i in range(5)
    )
    small_base = OrgState(teams=small_teams, workload=3, domains=roof)
    small_claimed = OrgState(
        teams=small_teams,
        workload=3,
        domains=roof,
        claims=(AuthorityClaim("chapter", "t0"),),
    )
    small_cost = evaluate(small_base).value - evaluate(small_claimed).value
    assert small_cost > cost


def test_c16_shed_load_follows_the_wiring():
    """A disconnected authority absorbs nothing: no laundering a queue."""
    founder = Team("founder", "Founder", True, headcount=8)
    subs = tuple(Team(f"t{i}", f"T{i}", False, headcount=8) for i in range(10))
    deps = tuple(Dependency("founder", f"t{i}", 1) for i in range(10))
    saturated = OrgState(teams=(founder,) + subs, dependencies=deps, workload=3)
    puppet = Team("puppet", "Puppet", True, headcount=1)
    laundered = OrgState(teams=(founder, puppet) + subs, dependencies=deps, workload=3)
    before = scale_context(saturated, _PARAMS)
    after = scale_context(laundered, _PARAMS)
    assert after.inflow["puppet"] == 0.0
    assert after.inflow["founder"] == before.inflow["founder"]
    # Unwired escalators still fall back to an equal split, so a structure
    # with no edges keeps its centre loaded (C11's fixture relies on it).
    edgeless = OrgState(teams=(founder, puppet) + subs, workload=3)
    fallback = scale_context(edgeless, _PARAMS)
    assert fallback.inflow["founder"] > 0.0
    assert fallback.inflow["puppet"] == fallback.inflow["founder"]


def test_c17_a_roof_needs_an_officer():
    """Two sovereigns alone under a nominal roof are still unowned."""
    roof = (Domain("c", "Company"),)
    duo = OrgState(
        teams=(
            Team("a", "A", True, domain_id="c", headcount=3_000),
            Team("b", "B", True, domain_id="c", headcount=3_000),
        ),
        dependencies=(Dependency("a", "b", 0),),
        workload=1,
        domains=roof,
    )
    duo_context = scale_context(duo, _PARAMS)
    assert duo_context.unowned["a"] == 1
    assert duo_context.unowned["b"] == 1
    officer = Team("officer", "Officer", True, domain_id="c", headcount=10)
    trio = OrgState(
        teams=duo.teams + (officer,),
        dependencies=duo.dependencies,
        workload=1,
        domains=roof,
    )
    trio_context = scale_context(trio, _PARAMS)
    assert all(count == 0 for count in trio_context.unowned.values())
    assert evaluate(trio).value > evaluate(duo).value
