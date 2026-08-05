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
class ClaimSpec:
    """A plain authority-claim description: claimant contests subject."""

    claimant: str
    subject: str


@dataclass(frozen=True, slots=True)
class ExampleSummary:
    """A loadable example organisation: its menu label, note and lookup key."""

    key: str
    label: str
    note: str


@dataclass(frozen=True, slots=True)
class DomainSpec:
    """A plain domain description, as collected by the editor or an importer."""

    id: str
    name: str
    parent_id: str | None = None
    lead: str = ""
    category: str = DEFAULT_CATEGORY
    headcount: int = 0


@dataclass(frozen=True, slots=True)
class OrgBlueprint:
    """A plain description of an org, before domain validation."""

    teams: tuple[TeamSpec, ...]
    dependencies: tuple[DependencySpec, ...] = ()
    workload: int = 1
    domains: tuple[DomainSpec, ...] = ()
    claims: tuple[ClaimSpec, ...] = ()


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
class SessionSnapshot:
    """A session as persisted: replaying moves from initial_org yields org.

    org is stored too so a reader that cannot replay (an older build, or a
    replay that no longer applies) still has the current organisation.

    focused_on carries the drilled section, so a session reopens where it was
    left rather than at the top level. It defaults to None, which is both the
    unfocused state and what an older file without the field restores as.
    """

    initial_org: OrgState
    moves: tuple[Move, ...]
    org: OrgState
    focused_on: str | None = None


@dataclass(frozen=True, slots=True)
class FrameAssessment:
    """A move judged within its own frame: the unit it acted inside.

    A locally great repair is worth almost nothing at whole-org scale, so
    the report carries this second verdict alongside the org-wide one for
    any move whose targets all sit inside one unit's subtree.
    """

    frame_label: str
    classification: MoveClassification
    score_before: float
    score_after: float


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One move in a plan, with its effect, attribution and justification.

    historic marks a move carried over from an earlier run of the app, so
    the report can separate the current run's work from the record. local
    is the move's verdict within its own frame, or None for an org-wide
    act with no frame of its own.
    """

    description: str
    classification: MoveClassification
    score_before: float
    score_after: float
    domain_id: str | None
    domain_label: str
    lead: str
    rationale: str
    historic: bool = False
    local: FrameAssessment | None = None


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
    contested_count: int = 0


@dataclass(frozen=True, slots=True)
class MapEdge:
    """An aggregated dependency between two nodes at a drill level."""

    source: str
    target: str
    weight: int
