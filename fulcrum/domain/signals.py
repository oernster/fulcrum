"""Signal definitions and readings: the lagging indicators to watch.

Each definition is domain metadata so the UI never hard-codes a glossary; the
same source feeds tooltips, the click-through definition card and the docs.
"""

from __future__ import annotations

from dataclasses import dataclass

from fulcrum.domain.models import OrgState
from fulcrum.domain.simulation import (
    DEFAULT_PARAMETERS,
    SimulationParameters,
    dependency_index,
    influence_load,
    team_capacity,
    team_imbalance,
)

_PERCENT: float = 100.0
# Floor on capacity used only to keep the queue-age ratio finite; real capacity
# is always strictly positive.
_MIN_CAPACITY: float = 1e-6

QUEUE_AGE = "handoff_queue_age"
ESCALATIONS = "escalations_per_release"
REWORK_RATE = "rework_rate"
INFLUENCE = "influence_without_authority"


@dataclass(frozen=True, slots=True)
class SignalDefinition:
    """Self-describing metadata for one lagging indicator."""

    key: str
    label: str
    gloss: str
    measures: str
    unit: str
    reads_high_when: str
    maps_to: str


SIGNAL_DEFINITIONS: tuple[SignalDefinition, ...] = (
    SignalDefinition(
        key=QUEUE_AGE,
        label="Handoff queue age",
        gloss=(
            "How long a change waits at a team boundary before the next "
            "team picks it up."
        ),
        measures="Mean turns of backlog waiting at a team boundary",
        unit="turns",
        reads_high_when="latency is piling up at that boundary",
        maps_to="the per-boundary decision queue (propagation delay)",
    ),
    SignalDefinition(
        key=ESCALATIONS,
        label="Escalations per release",
        gloss=(
            "Decisions pushed up to higher authority to get a single " "release out."
        ),
        measures="Teams that must escalate rather than decide locally",
        unit="count",
        reads_high_when="local authority is missing where the work happens",
        maps_to="broken authority worldlines",
    ),
    SignalDefinition(
        key=REWORK_RATE,
        label="Rework rate",
        gloss="Share of delivered work that comes back for redo soon after.",
        measures="Mean incentive skew across the teams",
        unit="percent",
        reads_high_when="decisions run on too narrow a light cone",
        maps_to="partial or stale information",
    ),
    SignalDefinition(
        key=INFLUENCE,
        label="Influence without authority",
        gloss=(
            "Teams that many others depend on but that cannot decide locally, "
            "so influence collects without the authority to use it. Left "
            "unchecked it burns people out."
        ),
        measures="Excess inbound dependence on teams that lack local authority",
        unit="load",
        reads_high_when=(
            "influence is concentrating on a team with no authority to wield it"
        ),
        maps_to="the decision shadow and phantom authority",
    ),
)

_DEFINITION_BY_KEY = {d.key: d for d in SIGNAL_DEFINITIONS}


def definition(key: str) -> SignalDefinition:
    """Look up a signal definition by its key."""
    return _DEFINITION_BY_KEY[key]


@dataclass(frozen=True, slots=True)
class SignalReading:
    """A computed signal value paired with its definition."""

    definition: SignalDefinition
    value: float


def compute_signals(
    org: OrgState, params: SimulationParameters = DEFAULT_PARAMETERS
) -> tuple[SignalReading, ...]:
    """Compute the current value of every signal for an org state."""
    index = dependency_index(org)
    team_count = len(org.teams)
    queue_age = (
        sum(
            team_imbalance(org, t, params, index)
            / max(_MIN_CAPACITY, team_capacity(org, t, params, index))
            for t in org.teams
        )
        / team_count
    )
    escalations = float(sum(1 for t in org.teams if not t.has_local_authority))
    rework = (sum(t.incentive_skew for t in org.teams) / team_count) * _PERCENT
    influence = influence_load(org, params, index)
    values = {
        QUEUE_AGE: queue_age,
        ESCALATIONS: escalations,
        REWORK_RATE: rework,
        INFLUENCE: influence,
    }
    return tuple(
        SignalReading(definition=d, value=values[d.key]) for d in SIGNAL_DEFINITIONS
    )
