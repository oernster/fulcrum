"""Structural evaluation: turn an org state into a 0..100 health score.

The model is deterministic and bounded. Each team has a resolution capacity
that falls when it lacks local authority, when it is heavily coupled and when
its incentives are skewed. Effective arrivals rise with the propagation delay
on its incoming dependencies. System backlog (arrivals over capacity), the
share of teams without authority and the mean incentive skew become three
bounded penalties that compose into the score. A team many others depend on
but that cannot decide locally adds a further gentle penalty: the
influence-without-authority gap.

Clean concentration is priced by scale through the prince band (see
authority_scale): attenuated up to the Dunbar horizon, at parity across the
band and amplified with the log of the population above it, capped at the
survivor ceiling. Contested ownership is never attenuated at any scale.

This module remains the import surface for the whole model: the coefficient
and classification vocabulary lives in parameters and the scale rule in
authority_scale, re-exported here so callers need one import path.
"""

from __future__ import annotations

from dataclasses import dataclass

from fulcrum.domain.authority_scale import (
    ScaleContext,
    contest_scale_factor,
    frame_headcount,
    prince_scale_factor,
    scale_context,
    scaled_authority_penalty,
    scaled_contested_penalty,
)
from fulcrum.domain.models import OrgState, Team
from fulcrum.domain.parameters import (
    DEFAULT_PARAMETERS,
    DEFAULT_THRESHOLDS,
    ClassificationThresholds,
    MoveClassification,
    SimulationParameters,
    classify_delta,
)

__all__ = [
    "DEFAULT_PARAMETERS",
    "DEFAULT_THRESHOLDS",
    "ClassificationThresholds",
    "CouplingIndex",
    "MoveClassification",
    "ScaleContext",
    "SimulationParameters",
    "StructuralScore",
    "claim_load",
    "classify_delta",
    "contest_scale_factor",
    "coupling_of",
    "depended_upon",
    "dependency_index",
    "evaluate",
    "external_claimants",
    "frame_headcount",
    "incoming_delay",
    "influence_load",
    "influence_without_authority",
    "is_contested",
    "prince_scale_factor",
    "scale_context",
    "scaled_authority_penalty",
    "scaled_contested_penalty",
    "team_arrivals",
    "team_capacity",
    "team_imbalance",
]

_UNIT: float = 1.0
_ZERO: float = 0.0


@dataclass(frozen=True, slots=True)
class StructuralScore:
    """A structural-health score with its three penalty components."""

    value: float
    latency_penalty: float
    escalation_penalty: float
    rework_penalty: float


@dataclass(frozen=True, slots=True)
class CouplingIndex:
    """Per-team dependency aggregates, gathered in one pass over the edges.

    Scoring reads each team's coupling, mean incoming delay and inbound demand
    repeatedly; gathering them once turns the per-team dependency rescans into
    dictionary lookups, so scoring a section is linear in teams plus edges rather
    than their product. It is an optimisation only: each value equals what the
    on-demand helpers compute, so passing an index never changes a score.
    """

    coupling: dict[str, int]
    incoming_delay: dict[str, float]
    depended_upon: dict[str, int]
    claimants: dict[str, int]


def dependency_index(org: OrgState) -> CouplingIndex:
    """Gather every team's dependency aggregates in a single pass over the edges."""
    coupling = {team.id: 0 for team in org.teams}
    delay_sum = {team.id: 0 for team in org.teams}
    delay_count = {team.id: 0 for team in org.teams}
    depended = {team.id: 0 for team in org.teams}
    claimants = {team.id: 0 for team in org.teams}
    for dep in org.internal_dependencies():
        coupling[dep.upstream] += 1
        coupling[dep.downstream] += 1
        delay_sum[dep.downstream] += dep.propagation_delay
        delay_count[dep.downstream] += 1
        depended[dep.upstream] += 1
    for claim in org.claims:
        claimants[claim.subject] += 1
    incoming: dict[str, float] = {}
    for team_id, count in delay_count.items():
        incoming[team_id] = delay_sum[team_id] / count if count else _ZERO
    return CouplingIndex(coupling, incoming, depended, claimants)


def external_claimants(
    org: OrgState, team_id: str, index: CouplingIndex | None = None
) -> int:
    """How many external actors claim this team's decision class."""
    if index is not None:
        return index.claimants[team_id]
    return sum(1 for claim in org.claims if claim.subject == team_id)


def is_contested(org: OrgState, team: Team, index: CouplingIndex | None = None) -> bool:
    """Whether this team's decision class carries a standing claim.

    Every decision class already has a structural owner: the team itself when
    it decides locally, or the line it escalates to when it does not. That
    owner is claimant one, so any standing external claim makes two and the
    meta-question of who decides must be settled before anything can be
    decided. A claim is by definition unresolved: resolving one removes it.
    """
    return external_claimants(org, team.id, index) > 0


def claim_load(org: OrgState, index: CouplingIndex | None = None) -> float:
    """Total excess claimants across the org: one per standing claim.

    The structural owner is always claimant one, so every standing claim is
    one claimant beyond it. Zero when nothing is claimed, so an org without
    contest pays nothing here.
    """
    load = sum(external_claimants(org, team.id, index) for team in org.teams)
    return float(load)


def coupling_of(org: OrgState, team_id: str, index: CouplingIndex | None = None) -> int:
    """Number of dependencies that touch a team in either direction."""
    if index is not None:
        return index.coupling[team_id]
    return sum(1 for dep in org.internal_dependencies() if dep.touches(team_id))


def incoming_delay(
    org: OrgState, team_id: str, index: CouplingIndex | None = None
) -> float:
    """Mean propagation delay on the dependencies this team waits on."""
    if index is not None:
        return index.incoming_delay[team_id]
    delays = [
        d.propagation_delay
        for d in org.internal_dependencies()
        if d.downstream == team_id
    ]
    if not delays:
        return _ZERO
    return sum(delays) / len(delays)


def team_capacity(
    org: OrgState,
    team: Team,
    params: SimulationParameters = DEFAULT_PARAMETERS,
    index: CouplingIndex | None = None,
    scale_factor: float | None = None,
) -> float:
    """Decisions a team can clear per turn, after structural penalties.

    scale_factor is this team's pricing factor: a clean escalating team is
    priced at its resolution neighbourhood's population (scale_context);
    None computes it from the org, and callers scoring many teams pass the
    context's per-team value. A contested team pays its full flat contest
    price up to the band and a proportionally deepened one above it, so
    contest costs strictly more than clean escalation at every scale.
    """
    if scale_factor is None:
        # A hypothetical team outside the org prices at the frame factor.
        context = scale_context(org, params)
        scale_factor = context.factors.get(team.id, context.frame_factor)
    factor = scale_factor
    capacity = params.base_capacity
    if is_contested(org, team, index):
        capacity *= scaled_contested_penalty(params, factor)
    elif not team.has_local_authority:
        capacity *= scaled_authority_penalty(params, factor)
    capacity /= _UNIT + params.coupling_weight * coupling_of(org, team.id, index)
    capacity /= _UNIT + params.incentive_weight * team.incentive_skew
    excess_size = max(_ZERO, float(team.size - params.ideal_team_size))
    capacity /= _UNIT + params.cognitive_load_weight * excess_size
    return capacity


def team_arrivals(
    org: OrgState,
    team: Team,
    params: SimulationParameters = DEFAULT_PARAMETERS,
    index: CouplingIndex | None = None,
    inflow: float | None = None,
) -> float:
    """Effective decisions arriving per turn, inflated by incoming delay.

    inflow is the escalated load landing on this team's queue from the
    teams that resolve through it (scale_context); None computes it from
    the org, and callers scoring many teams pass the context's value.

    Demand also travels along dependencies: every team waiting on this one
    lands dependent_demand_weight of the frame's workload on its queue,
    authority notwithstanding. An empowered hub that dozens of teams wait
    on saturates exactly as a deciding centre does; a light fan-out stays
    free while capacity absorbs it, so the cost begins where the queue
    does (Little's law, and LatencyLab's serial-queue placement result).
    """
    if inflow is None:
        inflow = scale_context(org, params).inflow.get(team.id, _ZERO)
    delay = incoming_delay(org, team.id, index)
    demand = params.dependent_demand_weight * depended_upon(org, team.id, index)
    arrivals = org.workload * (_UNIT + params.delay_arrival_weight * delay + demand)
    return arrivals + inflow


def team_imbalance(
    org: OrgState,
    team: Team,
    params: SimulationParameters = DEFAULT_PARAMETERS,
    index: CouplingIndex | None = None,
    scale_factor: float | None = None,
    inflow: float | None = None,
) -> float:
    """Per-turn backlog growth for a team (arrivals over capacity, floored)."""
    if scale_factor is None or inflow is None:
        context = scale_context(org, params)
        if scale_factor is None:
            scale_factor = context.factors.get(team.id, context.frame_factor)
        if inflow is None:
            inflow = context.inflow.get(team.id, _ZERO)
    arrivals = team_arrivals(org, team, params, index, inflow)
    return max(_ZERO, arrivals - team_capacity(org, team, params, index, scale_factor))


def depended_upon(
    org: OrgState, team_id: str, index: CouplingIndex | None = None
) -> int:
    """Number of teams that wait on this team (it is their upstream)."""
    if index is not None:
        return index.depended_upon[team_id]
    return sum(1 for dep in org.internal_dependencies() if dep.upstream == team_id)


def influence_without_authority(
    org: OrgState,
    team: Team,
    params: SimulationParameters = DEFAULT_PARAMETERS,
    index: CouplingIndex | None = None,
) -> float:
    """Excess inbound dependence on a team that cannot decide locally.

    Zero whenever the team has local authority, so a properly empowered hub
    costs nothing; it grows only when teams pile onto a node that lacks the
    authority to decide for them, the influence-without-authority gap.
    """
    if team.has_local_authority:
        return _ZERO
    excess = depended_upon(org, team.id, index) - params.influence_tolerance
    return float(max(0, excess))


def influence_load(
    org: OrgState,
    params: SimulationParameters = DEFAULT_PARAMETERS,
    index: CouplingIndex | None = None,
) -> float:
    """Total influence-without-authority carried across the whole org."""
    return sum(influence_without_authority(org, t, params, index) for t in org.teams)


def evaluate(
    org: OrgState, params: SimulationParameters = DEFAULT_PARAMETERS
) -> StructuralScore:
    """Fold the structural penalties into a single 0..100 health score.

    The scale context is built once for the frame: each clean escalating
    team's charges (capacity penalty, escalation share, influence load)
    are priced at its resolution neighbourhood's population and its shed
    workload lands on its resolving authorities' queues, so a saturated
    centre registers as latency. A contested team cannot decide cleanly
    either (the meta-question of who decides escalates even when the team
    formally holds local authority), and its share is never attenuated,
    only amplified. Clean sovereigns facing each other across unowned
    interfaces drift toward the same share, priced at the frame's scale,
    and the influence gap divides the score by its per-team mean rather
    than its absolute total.
    """
    index = dependency_index(org)
    context = scale_context(org, params)
    team_count = len(org.teams)
    total_arrivals = sum(
        team_arrivals(org, t, params, index, context.inflow[t.id]) for t in org.teams
    )
    total_imbalance = sum(
        team_imbalance(
            org, t, params, index, context.factors[t.id], context.inflow[t.id]
        )
        for t in org.teams
    )
    latency = total_imbalance / total_arrivals
    # A clean sovereign on unowned interfaces cannot decide cleanly either:
    # its cross-team conflicts have no roof to resolve under, so each such
    # team drifts toward the escalation share in proportion to how many of
    # its interfaces are unowned, priced at the frame's scale. An escalating
    # or contested team never counts here too: the sets are disjoint.
    fragmentation = sum(
        min(_UNIT, params.unowned_interface_weight * count) * context.factors[team_id]
        for team_id, count in context.unowned.items()
        if count
    )
    escalation = min(
        _UNIT,
        (
            sum(
                context.factors[t.id]
                for t in org.teams
                if not t.has_local_authority or is_contested(org, t, index)
            )
            + fragmentation
        )
        / team_count,
    )
    rework = sum(t.incentive_skew for t in org.teams) / team_count
    penalty = (
        params.latency_weight * latency
        + params.escalation_weight * escalation
        + params.rework_weight * rework
    )
    value = params.max_score * (_UNIT - penalty)
    # The influence gap is priced as its share of the organisation, not as
    # an absolute count, so one overloaded hub costs a proportionate slice
    # of a large org's score rather than half of it.
    weighted_influence = sum(
        influence_without_authority(org, t, params, index) * context.factors[t.id]
        for t in org.teams
    )
    value /= _UNIT + params.influence_weight * weighted_influence / team_count
    # Claims divide by their per-team mean for the same reason: a matrix
    # overlay across a whole division is priced as the share of the org it
    # actually contests, not as an absolute count that dwarfs everything.
    value /= _UNIT + params.contested_weight * claim_load(org, index) / team_count
    return StructuralScore(
        value=max(_ZERO, min(params.max_score, value)),
        latency_penalty=latency,
        escalation_penalty=escalation,
        rework_penalty=rework,
    )
