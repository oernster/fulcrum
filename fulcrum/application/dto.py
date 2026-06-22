"""Data-transfer objects crossing the application boundary."""

from __future__ import annotations

from dataclasses import dataclass

from fulcrum.domain.models import DEFAULT_CATEGORY, DEFAULT_HEADCOUNT, OrgState
from fulcrum.domain.moves import Move
from fulcrum.domain.simulation import MoveClassification


@dataclass(frozen=True, slots=True)
class TeamSpec:
    """A plain team description, as collected by the editor or an importer."""

    id: str
    name: str
    has_local_authority: bool
    incentive_skew: float = 0.0
    domain_id: str | None = None
    size: int = 1
    owner: str = ""
    headcount: int = DEFAULT_HEADCOUNT


@dataclass(frozen=True, slots=True)
class DependencySpec:
    """A plain dependency description."""

    upstream: str
    downstream: str
    propagation_delay: int = 0


@dataclass(frozen=True, slots=True)
class DomainSpec:
    """A plain domain description, as collected by the editor or an importer."""

    id: str
    name: str
    parent_id: str | None = None
    lead: str = ""
    category: str = DEFAULT_CATEGORY


@dataclass(frozen=True, slots=True)
class OrgBlueprint:
    """A plain description of an org, before domain validation."""

    teams: tuple[TeamSpec, ...]
    dependencies: tuple[DependencySpec, ...] = ()
    workload: int = 1
    domains: tuple[DomainSpec, ...] = ()


@dataclass(frozen=True, slots=True)
class MoveValuation:
    """A move paired with its evaluated effect and classification."""

    move: Move
    score_before: float
    score_after: float
    classification: MoveClassification

    @property
    def delta(self) -> float:
        return self.score_after - self.score_before


@dataclass(frozen=True, slots=True)
class Plan:
    """A replayable plan: the starting org and the ordered moves played on it."""

    initial_org: OrgState
    moves: tuple[Move, ...]
    created_at: str


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One move in a plan, with its effect, attribution and justification."""

    description: str
    classification: MoveClassification
    score_before: float
    score_after: float
    domain_id: str | None
    domain_label: str
    lead: str
    rationale: str


@dataclass(frozen=True, slots=True)
class DomainRecommendation:
    """The moves a plan recommends within one domain, for its lead."""

    domain_id: str | None
    label: str
    lead: str
    steps: tuple[PlanStep, ...]


@dataclass(frozen=True, slots=True)
class PlanReport:
    """A scored, justified, per-domain narrative of a completed plan."""

    start_score: float
    final_score: float
    steps: tuple[PlanStep, ...]
    recommendations: tuple[DomainRecommendation, ...]


@dataclass(frozen=True, slots=True)
class MapNode:
    """One node at a drill level of the org map: a domain box or a team."""

    kind: str
    id: str
    label: str
    team_count: int
    authority_ratio: float
    owner: str = ""
    category: str = ""
    headcount: int = 0


@dataclass(frozen=True, slots=True)
class MapEdge:
    """An aggregated dependency between two nodes at a drill level."""

    source: str
    target: str
    weight: int
