"""The authority-claim moves: resolving, downgrading and imposing contest.

These are the interventions on contested decision classes: pick a single
accountable owner (the great repair), turn a claimant into an explicit
consulted dependency (the honest RACI move) or overlay a second claimant on
every team (the canonical matrix blunder, the contest twin of the approval
layer). Pure transformations, registered in moves.py's dispatch table.
"""

from __future__ import annotations

from fulcrum.domain.errors import InvalidMoveError, UnknownTeamError
from fulcrum.domain.models import AuthorityClaim, Dependency, OrgState
from fulcrum.domain.move_base import Move

_RESOLVE_TARGET_COUNT = 2
_DOWNGRADE_TARGET_COUNT = 2

# A consulted actor is one turn of waiting on an explicit interface, not a
# co-owner of the decision class.
CONSULTATION_DELAY = 1

_OVERLAY_PREFIX = "overlay"


def _unique_overlay_label(org: OrgState) -> str:
    """The first overlay label unused as a team id or an existing claimant."""
    taken = set(org.team_ids) | {c.claimant for c in org.claims}
    index = 1
    candidate = f"{_OVERLAY_PREFIX}_{index}"
    while candidate in taken:
        index += 1
        candidate = f"{_OVERLAY_PREFIX}_{index}"
    return candidate


def resolve_authority(org: OrgState, move: Move) -> OrgState:
    """Collapse a decision class into a single accountable owner.

    Targets are (subject, winner). Every claim on the subject is removed
    either way: a standing claim is by definition unresolved contest.
    Resolving in favour of the subject grants it local authority; resolving
    in favour of a claimant strips it, so the class thereafter escalates to
    its new owner cleanly, one resolvable worldline either way.
    """
    if len(move.targets) != _RESOLVE_TARGET_COUNT:
        raise InvalidMoveError("resolve_authority needs a subject and a winner")
    subject_id, winner = move.targets
    if not org.has_team(subject_id):
        raise UnknownTeamError(f"move targets unknown team: {subject_id}")
    claimants = {claim.claimant for claim in org.claims_on(subject_id)}
    if winner != subject_id and winner not in claimants:
        raise InvalidMoveError(
            "the winner must be the team itself or a current claimant"
        )
    remaining = tuple(c for c in org.claims if c.subject != subject_id)
    wins_itself = winner == subject_id
    teams = tuple(
        t.with_authority(wins_itself) if t.id == subject_id else t for t in org.teams
    )
    return OrgState(
        teams=teams,
        dependencies=org.dependencies,
        workload=org.workload,
        origin=org.origin,
        domains=org.domains,
        claims=remaining,
    )


def downgrade_claim(org: OrgState, move: Move) -> OrgState:
    """Turn a claim into a consulted dependency: an interface, not authority.

    Targets are (claimant, subject). The claim is removed; when the claimant
    is a modelled node the consultation becomes an explicit dependency edge
    with a small delay, so the overhead is priced instead of hidden. An
    unmodelled claimant (a plain label) simply stops claiming.
    """
    if len(move.targets) != _DOWNGRADE_TARGET_COUNT:
        raise InvalidMoveError("downgrade_claim needs a claimant and a subject")
    claimant, subject = move.targets
    if not any(c.claimant == claimant and c.subject == subject for c in org.claims):
        raise InvalidMoveError("no such claim to downgrade")
    remaining = tuple(
        c for c in org.claims if not (c.claimant == claimant and c.subject == subject)
    )
    dependencies = org.dependencies
    known = set(org.team_ids) | {d.id for d in org.domains}
    already = any(
        d.upstream == claimant and d.downstream == subject for d in dependencies
    )
    if claimant in known and not already:
        dependencies = dependencies + (
            Dependency(claimant, subject, CONSULTATION_DELAY),
        )
    return OrgState(
        teams=org.teams,
        dependencies=dependencies,
        workload=org.workload,
        origin=org.origin,
        domains=org.domains,
        claims=remaining,
    )


def impose_matrix_overlay(org: OrgState, move: Move) -> OrgState:
    """Overlay a second claimant on every team: the canonical matrix blunder.

    The overlay actor claims every existing team's decision class, so every
    team becomes contested at once. The claimant is an unmodelled label,
    not a delivery team: a matrix overlay sits beside the delivery graph,
    so it neither dilutes the per-team means nor absorbs any escalated
    load. Nothing else changes, which isolates the mechanism: the damage
    is pure contest.
    """
    overlay_id = _unique_overlay_label(org)
    new_claims = tuple(AuthorityClaim(overlay_id, t.id) for t in org.teams)
    return OrgState(
        teams=org.teams,
        dependencies=org.dependencies,
        workload=org.workload,
        origin=org.origin,
        domains=org.domains,
        claims=org.claims + new_claims,
    )
