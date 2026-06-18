"""Structural moves: pure transformations from one org state to another."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fulcrum.domain.errors import InvalidMoveError, UnknownTeamError
from fulcrum.domain.models import Dependency, OrgState, Team

# Delay stamped on the dependencies created by an approval layer. A new gate
# that every team must route through is the canonical blunder.
_APPROVAL_GATE_DELAY: int = 3
_APPROVAL_GATE_PREFIX: str = "approval"

# Fraction of the original delay kept when interfaces are stabilised, and the
# fraction of incentive skew kept when incentives are realigned. Both pull a
# value toward zero without forcing it there.
_STABILISE_RETENTION: float = 0.4
_REALIGN_RETENTION: float = 0.4

_COLLAPSE_TARGET_COUNT: int = 2

# Growth moves act on a single named team. A split divides that team into two
# owners (so its dependencies are shared in half between them); adding an owner
# hands one of the team's dependencies to a brand-new accountable owner.
_GROWTH_TARGET_COUNT: int = 1
_SPLIT_OWNER_COUNT: int = 2
_ADDED_OWNER_INTAKE: int = 1
_MIN_TEAM_SIZE: int = 1
_MIN_HEADCOUNT: int = 1
_SPLIT_SIBLING_ID_SUFFIX: str = "_b"
_SPLIT_SIBLING_NAME_SUFFIX: str = " (split)"
_ADDED_OWNER_ID_SUFFIX: str = "_owner"
_ADDED_OWNER_NAME_SUFFIX: str = " (new owner)"


class MoveKind(str, Enum):
    """The structural interventions a player can make."""

    ADD_APPROVAL_LAYER = "add_approval_layer"
    STABILISE_INTERFACES = "stabilise_interfaces"
    DELEGATE_AUTHORITY = "delegate_authority"
    REALIGN_INCENTIVES = "realign_incentives"
    COLLAPSE_BOUNDARY = "collapse_boundary"
    SPLIT_TEAM = "split_team"
    ADD_TEAM = "add_team"


@dataclass(frozen=True, slots=True)
class Move:
    """A structural move: a kind plus the team ids it acts on."""

    kind: MoveKind
    targets: tuple[str, ...] = ()
    label: str = ""

    def display_label(self) -> str:
        return self.label or self.kind.value.replace("_", " ")


def apply_move(org: OrgState, move: Move) -> OrgState:
    """Return a new org state with the move applied. Pure."""
    for team_id in move.targets:
        if not org.has_team(team_id):
            raise UnknownTeamError(f"move targets unknown team: {team_id}")
    handler = _HANDLERS[move.kind]
    return handler(org, move)


def _add_approval_layer(org: OrgState, move: Move) -> OrgState:
    gate_id = _unique_gate_id(org)
    gate = Team(id=gate_id, name="Approval gate", has_local_authority=False)
    new_deps = tuple(Dependency(gate_id, t.id, _APPROVAL_GATE_DELAY) for t in org.teams)
    return OrgState(
        teams=org.teams + (gate,),
        dependencies=org.dependencies + new_deps,
        workload=org.workload,
        origin=org.origin,
        domains=org.domains,
    )


def _stabilise_interfaces(org: OrgState, move: Move) -> OrgState:
    new_deps = tuple(
        d.with_delay(int(d.propagation_delay * _STABILISE_RETENTION))
        for d in org.dependencies
    )
    return OrgState(org.teams, new_deps, org.workload, org.origin, org.domains)


def _delegate_authority(org: OrgState, move: Move) -> OrgState:
    targets = set(move.targets)
    if not targets:
        raise InvalidMoveError("delegate_authority needs at least one target")
    new_teams = tuple(
        t.with_authority(True) if t.id in targets else t for t in org.teams
    )
    return OrgState(new_teams, org.dependencies, org.workload, org.origin, org.domains)


def _realign_incentives(org: OrgState, move: Move) -> OrgState:
    targets = set(move.targets)
    if not targets:
        raise InvalidMoveError("realign_incentives needs at least one target")
    new_teams = tuple(
        (
            t.with_incentive_skew(t.incentive_skew * _REALIGN_RETENTION)
            if t.id in targets
            else t
        )
        for t in org.teams
    )
    return OrgState(new_teams, org.dependencies, org.workload, org.origin, org.domains)


def _collapse_boundary(org: OrgState, move: Move) -> OrgState:
    if len(move.targets) != _COLLAPSE_TARGET_COUNT:
        raise InvalidMoveError("collapse_boundary needs exactly two targets")
    keep_id, drop_id = move.targets
    keep = org.team(keep_id)
    drop = org.team(drop_id)
    merged = Team(
        id=keep_id,
        name=f"{keep.name} + {drop.name}",
        has_local_authority=keep.has_local_authority or drop.has_local_authority,
        incentive_skew=min(keep.incentive_skew, drop.incentive_skew),
        domain_id=keep.domain_id,
        size=keep.size + drop.size,
        owner=keep.owner,
        headcount=keep.headcount + drop.headcount,
    )
    new_teams = tuple(
        merged if t.id == keep_id else t for t in org.teams if t.id != drop_id
    )
    new_deps = _remap_dependencies(org.dependencies, drop_id, keep_id)
    return OrgState(new_teams, new_deps, org.workload, org.origin, org.domains)


def _remap_dependencies(
    deps: tuple[Dependency, ...], drop_id: str, keep_id: str
) -> tuple[Dependency, ...]:
    remapped: list[Dependency] = []
    seen: set[tuple[str, str]] = set()
    for dep in deps:
        up = keep_id if dep.upstream == drop_id else dep.upstream
        down = keep_id if dep.downstream == drop_id else dep.downstream
        if up == down:
            continue
        key = (up, down)
        if key in seen:
            continue
        seen.add(key)
        remapped.append(Dependency(up, down, dep.propagation_delay))
    return tuple(remapped)


def _split_team(org: OrgState, move: Move) -> OrgState:
    if len(move.targets) != _GROWTH_TARGET_COUNT:
        raise InvalidMoveError("split_team needs exactly one target")
    (team_id,) = move.targets
    source = org.team(team_id)
    sibling_id = _unique_team_id(org, f"{team_id}{_SPLIT_SIBLING_ID_SUFFIX}")
    sibling_size = max(_MIN_TEAM_SIZE, source.size // _SPLIT_OWNER_COUNT)
    source_size = max(_MIN_TEAM_SIZE, source.size - sibling_size)
    sibling_headcount = max(_MIN_HEADCOUNT, source.headcount // _SPLIT_OWNER_COUNT)
    source_headcount = max(_MIN_HEADCOUNT, source.headcount - sibling_headcount)
    sibling = Team(
        id=sibling_id,
        name=f"{source.name}{_SPLIT_SIBLING_NAME_SUFFIX}",
        has_local_authority=source.has_local_authority,
        incentive_skew=source.incentive_skew,
        domain_id=source.domain_id,
        size=sibling_size,
        owner=source.owner,
        headcount=sibling_headcount,
    )
    touching = sorted((d for d in org.dependencies if d.touches(team_id)), key=_dep_key)
    untouched = tuple(d for d in org.dependencies if not d.touches(team_id))
    kept_count = len(touching) // _SPLIT_OWNER_COUNT
    kept = tuple(touching[:kept_count])
    moved = tuple(_repoint(d, team_id, sibling_id) for d in touching[kept_count:])
    resized = tuple(
        (
            t.with_size(source_size).with_headcount(source_headcount)
            if t.id == team_id
            else t
        )
        for t in org.teams
    )
    return OrgState(
        teams=resized + (sibling,),
        dependencies=untouched + kept + moved,
        workload=org.workload,
        origin=org.origin,
        domains=org.domains,
    )


def _add_team(org: OrgState, move: Move) -> OrgState:
    if len(move.targets) != _GROWTH_TARGET_COUNT:
        raise InvalidMoveError("add_team needs exactly one target")
    (team_id,) = move.targets
    source = org.team(team_id)
    owner_id = _unique_team_id(org, f"{team_id}{_ADDED_OWNER_ID_SUFFIX}")
    owner = Team(
        id=owner_id,
        name=f"{source.name}{_ADDED_OWNER_NAME_SUFFIX}",
        has_local_authority=True,
        domain_id=source.domain_id,
    )
    touching = sorted((d for d in org.dependencies if d.touches(team_id)), key=_dep_key)
    untouched = tuple(d for d in org.dependencies if not d.touches(team_id))
    handed_over = tuple(
        _repoint(d, team_id, owner_id) for d in touching[:_ADDED_OWNER_INTAKE]
    )
    retained = tuple(touching[_ADDED_OWNER_INTAKE:])
    return OrgState(
        teams=org.teams + (owner,),
        dependencies=untouched + retained + handed_over,
        workload=org.workload,
        origin=org.origin,
        domains=org.domains,
    )


def _dep_key(dep: Dependency) -> tuple[str, str, int]:
    return (dep.upstream, dep.downstream, dep.propagation_delay)


def _repoint(dep: Dependency, old_id: str, new_id: str) -> Dependency:
    upstream = new_id if dep.upstream == old_id else dep.upstream
    downstream = new_id if dep.downstream == old_id else dep.downstream
    return Dependency(upstream, downstream, dep.propagation_delay)


def _unique_team_id(org: OrgState, base: str) -> str:
    existing = set(org.team_ids)
    candidate = base
    index = 1
    while candidate in existing:
        index += 1
        candidate = f"{base}_{index}"
    return candidate


def _unique_gate_id(org: OrgState) -> str:
    existing = set(org.team_ids)
    index = 1
    candidate = f"{_APPROVAL_GATE_PREFIX}_{index}"
    while candidate in existing:
        index += 1
        candidate = f"{_APPROVAL_GATE_PREFIX}_{index}"
    return candidate


_HANDLERS = {
    MoveKind.ADD_APPROVAL_LAYER: _add_approval_layer,
    MoveKind.STABILISE_INTERFACES: _stabilise_interfaces,
    MoveKind.DELEGATE_AUTHORITY: _delegate_authority,
    MoveKind.REALIGN_INCENTIVES: _realign_incentives,
    MoveKind.COLLAPSE_BOUNDARY: _collapse_boundary,
    MoveKind.SPLIT_TEAM: _split_team,
    MoveKind.ADD_TEAM: _add_team,
}
