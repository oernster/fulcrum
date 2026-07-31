"""Tunable coefficients, classification bands and the move-quality vocabulary.

Every coefficient of the structural model lives on SimulationParameters, so
there are no hidden constants. The scale-dependent authority coefficients
(the prince band) are validated here with the rest; the factor they shape is
computed in authority_scale and applied in simulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fulcrum.domain.errors import InvalidOrgStateError

_UNIT: float = 1.0
_ZERO: float = 0.0
_WEIGHT_SUM_TOLERANCE: float = 1e-9
_MIN_IDEAL_TEAM_SIZE: int = 1
_MIN_INFLUENCE_TOLERANCE: int = 0
_MIN_DUNBAR_HEADCOUNT: int = 1


@dataclass(frozen=True, slots=True)
class SimulationParameters:
    """Tunable coefficients for the structural model (no hidden constants).

    The prince-band coefficients price concentrated authority by scale.
    Up to dunbar_headcount people a single centre's light cone covers the
    whole organisation, so clean concentration costs only prince_attenuation
    of its flat price; across the band to prince_band_upper the price rises
    to parity; above it the price grows with the log of the population by
    prince_amplification per decade, capped at prince_survivor_ceiling so
    concentration at scale is a graded penalty, never a prohibition.

    escalation_load_share is the fraction of an escalating team's workload
    that lands on its resolving authorities' queues. It is deliberately not
    attenuated by the prince band: the band forgives communication friction
    at small scale, never decision bandwidth, so a centre absorbing thirty
    teams' escalations saturates however small the organisation is.

    unowned_interface_weight prices fragmentation: a dependency between two
    clean sovereigns that share no enclosing domain has no institutional
    roof under which its conflicts can be arbitrated, so each such edge
    pushes its endpoints toward the cannot-decide-cleanly share, scaled by
    the prince factor. Two founders across a desk stay cheap; a roofless
    sovereign network at scale does not.
    """

    base_capacity: float = 12.0
    authority_penalty: float = 0.45
    contested_penalty: float = 0.35
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
    contested_weight: float = 0.1
    max_score: float = 100.0
    dunbar_headcount: int = 150
    prince_band_upper: int = 200
    prince_attenuation: float = 0.3
    prince_amplification: float = 0.25
    prince_survivor_ceiling: float = 1.6
    escalation_load_share: float = 0.25
    unowned_interface_weight: float = 0.5

    def __post_init__(self) -> None:
        if self.base_capacity <= _ZERO:
            raise InvalidOrgStateError("base_capacity must be positive")
        if not _ZERO < self.authority_penalty <= _UNIT:
            raise InvalidOrgStateError("authority_penalty must be in (0, 1]")
        # Contest may never be cheaper than clean escalation: an escalating
        # team has a resolvable worldline, a contested one does not.
        if not _ZERO < self.contested_penalty <= self.authority_penalty:
            raise InvalidOrgStateError(
                "contested_penalty must be in (0, authority_penalty]"
            )
        if self.contested_weight < _ZERO:
            raise InvalidOrgStateError("contested_weight must not be negative")
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
        self._validate_prince_band()

    def _validate_prince_band(self) -> None:
        if self.dunbar_headcount < _MIN_DUNBAR_HEADCOUNT:
            raise InvalidOrgStateError(
                f"dunbar_headcount must be at least {_MIN_DUNBAR_HEADCOUNT}"
            )
        if self.prince_band_upper <= self.dunbar_headcount:
            raise InvalidOrgStateError(
                "prince_band_upper must be above dunbar_headcount"
            )
        if not _ZERO < self.prince_attenuation <= _UNIT:
            raise InvalidOrgStateError("prince_attenuation must be in (0, 1]")
        if self.prince_amplification < _ZERO:
            raise InvalidOrgStateError("prince_amplification must not be negative")
        if self.prince_survivor_ceiling < _UNIT:
            raise InvalidOrgStateError("prince_survivor_ceiling must be at least 1")
        # The ceiling must keep an escalating team's capacity strictly
        # positive: survivorship means rare princes at scale exist, so scale
        # can never annihilate capacity outright.
        headroom = self.prince_survivor_ceiling * (_UNIT - self.authority_penalty)
        if headroom >= _UNIT:
            raise InvalidOrgStateError(
                "prince_survivor_ceiling must keep escalation capacity positive"
            )
        if not _ZERO <= self.escalation_load_share <= _UNIT:
            raise InvalidOrgStateError("escalation_load_share must be in [0, 1]")
        if self.unowned_interface_weight < _ZERO:
            raise InvalidOrgStateError("unowned_interface_weight must not be negative")


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
