"""Core organisational value objects: teams, dependencies and the org state.

All types are immutable (frozen, slots) and validate their own invariants on
construction. Collections are tuples so a state can be hashed and shared safely.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fulcrum.domain.errors import InvalidOrgStateError, UnknownTeamError

# Bounds for the incentive-skew value. 0 means local incentives are fully
# aligned with the system outcome; 1 means they pull entirely against it.
_MIN_SKEW: float = 0.0
_MAX_SKEW: float = 1.0

# A team's size in atomic units: 1 is a single base team, and collapsing teams
# together grows it. It is the cognitive-load proxy the simulator penalises once
# a unit grows past the comfortable band.
_MIN_TEAM_SIZE: int = 1

# A team's headcount: the number of people in it. Headcount rolls up through the
# domain hierarchy into the org total, so a structure can model 100k+ people
# without a rendered node per person. It is descriptive and does not affect the
# structural score.
DEFAULT_HEADCOUNT: int = 8
_MIN_HEADCOUNT: int = 1

# The vocabulary of group tiers offered when modelling an org, largest first.
# A grouping can be any of these or a custom label, and they nest to any depth;
# a generated hierarchy aligns its leaves to the smallest tier and reads up
# toward the company, so a shallow org uses the lower tiers and only a deep one
# reaches Company. The category is descriptive: it names what a grouping is, it
# does not change the score.
GROUP_CATEGORIES: tuple[str, ...] = (
    "Company",
    "Group",
    "Division",
    "Department",
    "Domain",
)
DEFAULT_CATEGORY: str = "Domain"


class Origin(str, Enum):
    """Where an organisational state came from."""

    GENERATED = "generated"
    IMPORTED = "imported"
    WIZARD = "wizard"


@dataclass(frozen=True, slots=True)
class Team:
    """A team or role: a node that holds (or lacks) local decision authority."""

    id: str
    name: str
    has_local_authority: bool
    incentive_skew: float = _MIN_SKEW
    domain_id: str | None = None
    size: int = _MIN_TEAM_SIZE
    owner: str = ""
    headcount: int = DEFAULT_HEADCOUNT

    def __post_init__(self) -> None:
        if not self.id:
            raise InvalidOrgStateError("team id must be a non-empty string")
        if not self.name:
            raise InvalidOrgStateError("team name must be a non-empty string")
        if not _MIN_SKEW <= self.incentive_skew <= _MAX_SKEW:
            raise InvalidOrgStateError(
                f"incentive_skew must be between {_MIN_SKEW} and {_MAX_SKEW}"
            )
        if self.size < _MIN_TEAM_SIZE:
            raise InvalidOrgStateError(f"team size must be at least {_MIN_TEAM_SIZE}")
        if self.headcount < _MIN_HEADCOUNT:
            raise InvalidOrgStateError(
                f"team headcount must be at least {_MIN_HEADCOUNT}"
            )

    def with_authority(self, value: bool) -> "Team":
        return Team(
            self.id,
            self.name,
            value,
            self.incentive_skew,
            self.domain_id,
            self.size,
            self.owner,
            self.headcount,
        )

    def with_incentive_skew(self, value: float) -> "Team":
        return Team(
            self.id,
            self.name,
            self.has_local_authority,
            value,
            self.domain_id,
            self.size,
            self.owner,
            self.headcount,
        )

    def with_size(self, value: int) -> "Team":
        return Team(
            self.id,
            self.name,
            self.has_local_authority,
            self.incentive_skew,
            self.domain_id,
            value,
            self.owner,
            self.headcount,
        )

    def with_headcount(self, value: int) -> "Team":
        return Team(
            self.id,
            self.name,
            self.has_local_authority,
            self.incentive_skew,
            self.domain_id,
            self.size,
            self.owner,
            value,
        )

    def with_owner(self, value: str) -> "Team":
        return Team(
            self.id,
            self.name,
            self.has_local_authority,
            self.incentive_skew,
            self.domain_id,
            self.size,
            value,
            self.headcount,
        )


@dataclass(frozen=True, slots=True)
class Dependency:
    """A directed dependency: downstream waits on upstream, with a delay."""

    upstream: str
    downstream: str
    propagation_delay: int = 0

    def __post_init__(self) -> None:
        if not self.upstream or not self.downstream:
            raise InvalidOrgStateError("dependency endpoints must be non-empty")
        if self.upstream == self.downstream:
            raise InvalidOrgStateError("a team cannot depend on itself")
        if self.propagation_delay < 0:
            raise InvalidOrgStateError("propagation_delay must not be negative")

    def touches(self, team_id: str) -> bool:
        return self.upstream == team_id or self.downstream == team_id

    def with_delay(self, value: int) -> "Dependency":
        return Dependency(self.upstream, self.downstream, value)


@dataclass(frozen=True, slots=True)
class Domain:
    """A bounded context grouping teams (and sub-domains) within the org.

    Domains nest to any depth through parent_id, forming the hierarchy a large
    org is navigated and recommended through. lead names the senior owner the
    CTO would hand this domain's recommendations to. headcount is the unit's own
    population, which the hierarchy queries roll up; it is zero for a unit whose
    people are counted by its teams instead.
    """

    id: str
    name: str
    parent_id: str | None = None
    lead: str = ""
    category: str = DEFAULT_CATEGORY
    headcount: int = 0

    def __post_init__(self) -> None:
        if not self.id:
            raise InvalidOrgStateError("domain id must be a non-empty string")
        if not self.name:
            raise InvalidOrgStateError("domain name must be a non-empty string")
        if self.parent_id == self.id:
            raise InvalidOrgStateError("a domain cannot be its own parent")


@dataclass(frozen=True, slots=True)
class OrgState:
    """A structural position: teams, their dependencies and the workload."""

    teams: tuple[Team, ...]
    dependencies: tuple[Dependency, ...] = ()
    workload: int = 1
    origin: Origin = Origin.GENERATED
    domains: tuple[Domain, ...] = ()

    def __post_init__(self) -> None:
        if not self.teams:
            raise InvalidOrgStateError("an org state needs at least one team")
        ids = [t.id for t in self.teams]
        if len(ids) != len(set(ids)):
            raise InvalidOrgStateError("team ids must be unique")
        known = set(ids)
        for dep in self.dependencies:
            if dep.upstream not in known or dep.downstream not in known:
                raise InvalidOrgStateError("dependency references an unknown team")
        if self.workload <= 0:
            raise InvalidOrgStateError("workload must be a positive integer")
        self._validate_domains()

    def _validate_domains(self) -> None:
        domain_ids = [d.id for d in self.domains]
        if len(domain_ids) != len(set(domain_ids)):
            raise InvalidOrgStateError("domain ids must be unique")
        known_domains = set(domain_ids)
        for team in self.teams:
            if team.domain_id is not None and team.domain_id not in known_domains:
                raise InvalidOrgStateError(
                    f"team references an unknown domain: {team.domain_id}"
                )
        for domain in self.domains:
            if domain.parent_id is not None and domain.parent_id not in known_domains:
                raise InvalidOrgStateError(
                    f"domain references an unknown parent: {domain.parent_id}"
                )
        self._check_acyclic()

    def _check_acyclic(self) -> None:
        parent_of = {d.id: d.parent_id for d in self.domains}
        for start in parent_of:
            seen: set[str] = set()
            current: str | None = start
            while current is not None:
                if current in seen:
                    raise InvalidOrgStateError("domain hierarchy must be acyclic")
                seen.add(current)
                current = parent_of.get(current)

    @property
    def team_ids(self) -> tuple[str, ...]:
        return tuple(t.id for t in self.teams)

    def team(self, team_id: str) -> Team:
        for t in self.teams:
            if t.id == team_id:
                return t
        raise UnknownTeamError(f"unknown team: {team_id}")

    def has_team(self, team_id: str) -> bool:
        return any(t.id == team_id for t in self.teams)
