"""Structural moves: pure transformations from one org state to another.

The vocabulary (MoveKind, Move) lives in move_base and the claim moves in
moves_claims; this module holds the structural handlers and the dispatch
table, re-exporting the vocabulary so callers import everything from here.
"""

from __future__ import annotations

from fulcrum.domain.errors import InvalidMoveError, UnknownTeamError
from fulcrum.domain.hierarchy import domain_subtree_ids
from fulcrum.domain.models import AuthorityClaim, Dependency, OrgState, Team
from fulcrum.domain.move_base import (
    Move,
    MoveKind,
    dep_sort_key,
    repoint,
    unique_prefixed_id,
    unique_team_id,
)
from fulcrum.domain.moves_claims import (
    downgrade_claim,
    impose_matrix_overlay,
    resolve_authority,
)

# Delay stamped on the dependencies created by an approval layer. A new gate
# that every team must route through is the canonical blunder.
APPROVAL_GATE_DELAY: int = 3
_APPROVAL_GATE_PREFIX: str = "approval"

# Fraction of the original delay kept when interfaces are stabilised, and the
# fraction of incentive skew kept when incentives are realigned. Both pull a
# value toward zero without forcing it there.
STABILISE_RETENTION: float = 0.4
REALIGN_RETENTION: float = 0.4

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

# These kinds carry targets that are not plain team ids (a claimant may be a
# domain or a label; a scoped stabilise names frame nodes, units included), so
# their handlers validate their own targets instead of the team-id check the
# other structural moves share.
_SELF_VALIDATING_KINDS = frozenset(
    {
        MoveKind.RESOLVE_AUTHORITY,
        MoveKind.DOWNGRADE_CLAIM,
        MoveKind.STABILISE_INTERFACES,
    }
)


def apply_move(org: OrgState, move: Move) -> OrgState:
    """Return a new org state with the move applied. Pure.

    Target validation builds the team-id set once (O(teams)) and tests each
    target against it, so an aggregate move that translates to thousands of
    targets stays linear rather than scanning every team per target. That
    quadratic was what stalled the UI when playing or previewing a move at a
    high scope of a very large org.
    """
    if move.kind not in _SELF_VALIDATING_KINDS:
        known_team_ids = {team.id for team in org.teams}
        for team_id in move.targets:
            if team_id not in known_team_ids:
                raise UnknownTeamError(f"move targets unknown team: {team_id}")
    handler = _HANDLERS[move.kind]
    return handler(org, move)


def _add_approval_layer(org: OrgState, move: Move) -> OrgState:
    gate_id = unique_prefixed_id(org, _APPROVAL_GATE_PREFIX)
    gate = Team(id=gate_id, name="Approval gate", has_local_authority=False)
    new_deps = tuple(Dependency(gate_id, t.id, APPROVAL_GATE_DELAY) for t in org.teams)
    return OrgState(
        teams=org.teams + (gate,),
        dependencies=org.dependencies + new_deps,
        workload=org.workload,
        origin=org.origin,
        domains=org.domains,
        claims=org.claims,
    )


def _stabilise_interfaces(org: OrgState, move: Move) -> OrgState:
    """Thin the interfaces of one frame, or of everything when untargeted.

    Targets are the frame's node ids (teams, or whole units standing as the
    frame's actors); only a dependency crossing between two distinct targeted
    scopes is thinned, exactly the edges that frame prices. An untargeted
    move keeps the legacy meaning (every dependency), so saved plans replay
    unchanged.
    """
    if move.targets:
        new_deps = _stabilise_scoped(org, move.targets)
    else:
        new_deps = tuple(
            d.with_delay(int(d.propagation_delay * STABILISE_RETENTION))
            for d in org.dependencies
        )
    return OrgState(
        org.teams, new_deps, org.workload, org.origin, org.domains, org.claims
    )


def _stabilise_scoped(org: OrgState, targets: tuple[str, ...]) -> tuple:
    domain_ids = {d.id for d in org.domains}
    owner: dict[str, str] = {}
    for node_id in targets:
        if org.has_team(node_id):
            owner[node_id] = node_id
        elif node_id in domain_ids:
            ids = domain_subtree_ids(org, node_id)
            for covered in ids:
                owner[covered] = node_id
            for team in org.teams:
                if team.domain_id in ids:
                    owner[team.id] = node_id
        else:
            raise UnknownTeamError(f"move targets unknown node: {node_id}")
    thinned = []
    for dep in org.dependencies:
        up = owner.get(dep.upstream)
        down = owner.get(dep.downstream)
        if up is not None and down is not None and up != down:
            thinned.append(
                dep.with_delay(int(dep.propagation_delay * STABILISE_RETENTION))
            )
        else:
            thinned.append(dep)
    return tuple(thinned)


def _delegate_authority(org: OrgState, move: Move) -> OrgState:
    targets = set(move.targets)
    if not targets:
        raise InvalidMoveError("delegate_authority needs at least one target")
    new_teams = tuple(
        t.with_authority(True) if t.id in targets else t for t in org.teams
    )
    return OrgState(
        new_teams, org.dependencies, org.workload, org.origin, org.domains, org.claims
    )


def _realign_incentives(org: OrgState, move: Move) -> OrgState:
    targets = set(move.targets)
    if not targets:
        raise InvalidMoveError("realign_incentives needs at least one target")
    new_teams = tuple(
        (
            t.with_incentive_skew(t.incentive_skew * REALIGN_RETENTION)
            if t.id in targets
            else t
        )
        for t in org.teams
    )
    return OrgState(
        new_teams, org.dependencies, org.workload, org.origin, org.domains, org.claims
    )


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
    new_claims = _remap_claims(org.claims, drop_id, keep_id)
    return OrgState(
        new_teams, new_deps, org.workload, org.origin, org.domains, new_claims
    )


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


def _remap_claims(
    claims: tuple[AuthorityClaim, ...], drop_id: str, keep_id: str
) -> tuple[AuthorityClaim, ...]:
    """Claims after a merge: endpoints renamed, self-claims and dupes dropped."""
    remapped: list[AuthorityClaim] = []
    seen: set[tuple[str, str]] = set()
    for claim in claims:
        claimant = keep_id if claim.claimant == drop_id else claim.claimant
        subject = keep_id if claim.subject == drop_id else claim.subject
        if claimant == subject:
            continue
        key = (claimant, subject)
        if key in seen:
            continue
        seen.add(key)
        remapped.append(AuthorityClaim(claimant, subject))
    return tuple(remapped)


def _split_team(org: OrgState, move: Move) -> OrgState:
    if len(move.targets) != _GROWTH_TARGET_COUNT:
        raise InvalidMoveError("split_team needs exactly one target")
    (team_id,) = move.targets
    source = org.team(team_id)
    sibling_id = unique_team_id(org, f"{team_id}{_SPLIT_SIBLING_ID_SUFFIX}")
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
    touching = sorted(
        (d for d in org.dependencies if d.touches(team_id)), key=dep_sort_key
    )
    untouched = tuple(d for d in org.dependencies if not d.touches(team_id))
    kept_count = len(touching) // _SPLIT_OWNER_COUNT
    kept = tuple(touching[:kept_count])
    moved = tuple(repoint(d, team_id, sibling_id) for d in touching[kept_count:])
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
        claims=org.claims,
    )


def _add_team(org: OrgState, move: Move) -> OrgState:
    if len(move.targets) != _GROWTH_TARGET_COUNT:
        raise InvalidMoveError("add_team needs exactly one target")
    (team_id,) = move.targets
    source = org.team(team_id)
    owner_id = unique_team_id(org, f"{team_id}{_ADDED_OWNER_ID_SUFFIX}")
    owner = Team(
        id=owner_id,
        name=f"{source.name}{_ADDED_OWNER_NAME_SUFFIX}",
        has_local_authority=True,
        domain_id=source.domain_id,
    )
    touching = sorted(
        (d for d in org.dependencies if d.touches(team_id)), key=dep_sort_key
    )
    untouched = tuple(d for d in org.dependencies if not d.touches(team_id))
    handed_over = tuple(
        repoint(d, team_id, owner_id) for d in touching[:_ADDED_OWNER_INTAKE]
    )
    retained = tuple(touching[_ADDED_OWNER_INTAKE:])
    return OrgState(
        teams=org.teams + (owner,),
        dependencies=untouched + retained + handed_over,
        workload=org.workload,
        origin=org.origin,
        domains=org.domains,
        claims=org.claims,
    )


_HANDLERS = {
    MoveKind.ADD_APPROVAL_LAYER: _add_approval_layer,
    MoveKind.STABILISE_INTERFACES: _stabilise_interfaces,
    MoveKind.DELEGATE_AUTHORITY: _delegate_authority,
    MoveKind.REALIGN_INCENTIVES: _realign_incentives,
    MoveKind.COLLAPSE_BOUNDARY: _collapse_boundary,
    MoveKind.SPLIT_TEAM: _split_team,
    MoveKind.ADD_TEAM: _add_team,
    MoveKind.RESOLVE_AUTHORITY: resolve_authority,
    MoveKind.DOWNGRADE_CLAIM: downgrade_claim,
    MoveKind.IMPOSE_MATRIX_OVERLAY: impose_matrix_overlay,
}
