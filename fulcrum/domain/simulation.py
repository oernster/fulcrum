"""Structural evaluation: turn an org state into a 0..100 health score.

The model is deterministic and bounded. Each team has a resolution capacity
that falls when it lacks local authority, when it is heavily coupled and when
its incentives are skewed. Effective arrivals rise with the propagation delay
on its incoming dependencies. System backlog (arrivals over capacity), the
share of teams without authority and the mean incentive skew become three
bounded penalties that compose into the score. A team many others depend on
but that cannot decide locally adds a further gentle penalty: the
influence-without-authority gap.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fulcrum.domain.errors import InvalidOrgStateError
from fulcrum.domain.models import OrgState, Team

_UNIT: float = 1.0
_ZERO: float = 0.0
_WEIGHT_SUM_TOLERANCE: float = 1e-9
_MIN_IDEAL_TEAM_SIZE: int = 1
_MIN_INFLUENCE_TOLERANCE: int = 0


@dataclass(frozen=True, slots=True)
class SimulationParameters:
    """Tunable coefficients for the structural model (no hidden constants)."""

    base_capacity: float = 12.0
    authority_penalty: float = 0.45
    coupling_weight: float = 0.6
    incentive_weight: float = 0.8
    delay_arrival_weight: float = 0.25
    latency_weight: float = 0.5
    escalation_weight: float = 0.3
    rework_weight: float = 0.2
    cognitive_load_weight: float = 0.6
    ideal_team_size: int = 3
    influence_weight: float = 0.08
    influence_tolerance: int = 1
    max_score: float = 100.0

    def __post_init__(self) -> None:
        if self.base_capacity <= _ZERO:
            raise InvalidOrgStateError("base_capacity must be positive")
        if not _ZERO < self.authority_penalty <= _UNIT:
            raise InvalidOrgStateError("authority_penalty must be in (0, 1]")
        weight_sum = self.latency_weight + self.escalation_weight + self.rework_weight
        if abs(weight_sum - _UNIT) > _WEIGHT_SUM_TOLERANCE:
            raise InvalidOrgStateError("penalty weights must sum to 1.0")
        if self.cognitive_load_weight < _ZERO:
            raise InvalidOrgStateError("cognitive_load_weight must not be negative")
        if self.ideal_team_size < _MIN_IDEAL_TEAM_SIZE:
            raise InvalidOrgStateError("ideal_team_size must be at least 1")
        if self.influence_weight < _ZERO:
            raise InvalidOrgStateError("influence_weight must not be negative")
        if self.influence_tolerance < _MIN_INFLUENCE_TOLERANCE:
            raise InvalidOrgStateError("influence_tolerance must not be negative")
        if self.max_score <= _ZERO:
            raise InvalidOrgStateError("max_score must be positive")


DEFAULT_PARAMETERS = SimulationParameters()


@dataclass(frozen=True, slots=True)
class ClassificationThresholds:
    """Score-delta bands that turn a move's effect into a classification."""

    great_delta: float = 9.0
    good_delta: float = 3.0
    blunder_delta: float = -1.0


DEFAULT_THRESHOLDS = ClassificationThresholds()


class MoveClassification(str, Enum):
    """How good a move is, judged purely by its effect on the score."""

    GREAT = "great"
    GOOD = "good"
    NEUTRAL = "neutral"
    BAD = "bad"
    BLUNDER = "blunder"


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


def dependency_index(org: OrgState) -> CouplingIndex:
    """Gather every team's dependency aggregates in a single pass over the edges."""
    coupling = {team.id: 0 for team in org.teams}
    delay_sum = {team.id: 0 for team in org.teams}
    delay_count = {team.id: 0 for team in org.teams}
    depended = {team.id: 0 for team in org.teams}
    for dep in org.internal_dependencies():
        coupling[dep.upstream] += 1
        coupling[dep.downstream] += 1
        delay_sum[dep.downstream] += dep.propagation_delay
        delay_count[dep.downstream] += 1
        depended[dep.upstream] += 1
    incoming: dict[str, float] = {}
    for team_id, count in delay_count.items():
        incoming[team_id] = delay_sum[team_id] / count if count else _ZERO
    return CouplingIndex(coupling, incoming, depended)


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
) -> float:
    """Decisions a team can clear per turn, after structural penalties."""
    capacity = params.base_capacity
    if not team.has_local_authority:
        capacity *= params.authority_penalty
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
) -> float:
    """Effective decisions arriving per turn, inflated by incoming delay."""
    delay = incoming_delay(org, team.id, index)
    return org.workload * (_UNIT + params.delay_arrival_weight * delay)


def team_imbalance(
    org: OrgState,
    team: Team,
    params: SimulationParameters = DEFAULT_PARAMETERS,
    index: CouplingIndex | None = None,
) -> float:
    """Per-turn backlog growth for a team (arrivals over capacity, floored)."""
    arrivals = team_arrivals(org, team, params, index)
    return max(_ZERO, arrivals - team_capacity(org, team, params, index))


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
    """Fold the structural penalties into a single 0..100 health score."""
    index = dependency_index(org)
    team_count = len(org.teams)
    total_arrivals = sum(team_arrivals(org, t, params, index) for t in org.teams)
    total_imbalance = sum(team_imbalance(org, t, params, index) for t in org.teams)
    latency = total_imbalance / total_arrivals
    escalation = sum(1 for t in org.teams if not t.has_local_authority) / team_count
    rework = sum(t.incentive_skew for t in org.teams) / team_count
    penalty = (
        params.latency_weight * latency
        + params.escalation_weight * escalation
        + params.rework_weight * rework
    )
    value = params.max_score * (_UNIT - penalty)
    value /= _UNIT + params.influence_weight * influence_load(org, params, index)
    return StructuralScore(
        value=max(_ZERO, min(params.max_score, value)),
        latency_penalty=latency,
        escalation_penalty=escalation,
        rework_penalty=rework,
    )


def classify_delta(
    delta: float, thresholds: ClassificationThresholds = DEFAULT_THRESHOLDS
) -> MoveClassification:
    """Map a score delta to a move classification."""
    if delta >= thresholds.great_delta:
        return MoveClassification.GREAT
    if delta >= thresholds.good_delta:
        return MoveClassification.GOOD
    if delta <= thresholds.blunder_delta:
        return MoveClassification.BLUNDER
    if delta < _ZERO:
        return MoveClassification.BAD
    return MoveClassification.NEUTRAL
