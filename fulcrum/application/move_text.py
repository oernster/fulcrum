"""Human-readable descriptions of moves, using team names for context.

Two delegate moves or two collapse moves are only distinguishable by who they
act on, so the board needs the team names, not just the move kind.
"""

from __future__ import annotations

from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, MoveKind
from fulcrum.shared.text import count_noun

_STABILISE_TEXT = "Stabilise all interfaces"
_APPROVAL_TEXT = "Add an approval layer"
_OVERLAY_TEXT = "Impose a matrix overlay"
# A frame-translated move can act on dozens of real teams; naming them all
# turns the last-move note into a wall of text, so the enumeration stops
# here and the rest is counted.
_MAX_NAMED_TARGETS = 3


def _named(org: OrgState, ids: tuple[str, ...]) -> str:
    names = [org.team(team_id).name for team_id in ids]
    if len(names) <= _MAX_NAMED_TARGETS:
        return " + ".join(names)
    shown = " + ".join(names[:_MAX_NAMED_TARGETS])
    return f"{shown} and {count_noun(len(names) - _MAX_NAMED_TARGETS, 'more team')}"


def _actor_name(org: OrgState, actor_id: str) -> str:
    """A claimant or winner's display name: team, unit or the raw label.

    A claimant need not be a modelled node at all (a chapter, a functional
    head), so anything unresolved renders as the label it was written as.
    """
    if org.has_team(actor_id):
        return org.team(actor_id).name
    for domain in org.domains:
        if domain.id == actor_id:
            return domain.name
    return actor_id


def describe_move(org: OrgState, move: Move) -> str:
    if move.kind == MoveKind.DELEGATE_AUTHORITY:
        return f"Delegate authority to {_named(org, move.targets)}"
    if move.kind == MoveKind.REALIGN_INCENTIVES:
        return f"Realign incentives at {_named(org, move.targets)}"
    if move.kind == MoveKind.COLLAPSE_BOUNDARY:
        return f"Collapse {_named(org, move.targets)}"
    if move.kind == MoveKind.STABILISE_INTERFACES:
        return _STABILISE_TEXT
    if move.kind == MoveKind.SPLIT_TEAM:
        return f"Split {_named(org, move.targets)} into two owners"
    if move.kind == MoveKind.ADD_TEAM:
        return f"Add a new owner beside {_named(org, move.targets)}"
    if move.kind == MoveKind.RESOLVE_AUTHORITY:
        subject, winner = move.targets
        if winner == subject:
            return f"Resolve authority at {_named(org, (subject,))} in its favour"
        return (
            f"Resolve authority at {_named(org, (subject,))} in favour of "
            f"{_actor_name(org, winner)}"
        )
    if move.kind == MoveKind.DOWNGRADE_CLAIM:
        claimant, subject = move.targets
        return (
            f"Downgrade {_actor_name(org, claimant)}'s claim on "
            f"{_named(org, (subject,))} to consultation"
        )
    if move.kind == MoveKind.IMPOSE_MATRIX_OVERLAY:
        return _OVERLAY_TEXT
    return _APPROVAL_TEXT


_MOVE_NOTES = {
    MoveKind.DELEGATE_AUTHORITY: (
        "Gives the team the right to decide locally, shortening its authority "
        "worldline and removing an escalation. Where many teams depend on it, "
        "it also dissolves influence that had collected without the authority "
        "to use it."
    ),
    MoveKind.REALIGN_INCENTIVES: (
        "Pulls the team's incentives back toward the system outcome, so less "
        "delivered work comes back as rework."
    ),
    MoveKind.STABILISE_INTERFACES: (
        "Thins and steadies the interfaces so changes cross team boundaries "
        "with less delay."
    ),
    MoveKind.COLLAPSE_BOUNDARY: (
        "Removes a boundary so one team owns the whole slice: it deletes a "
        "handoff, not headcount, so it is not centralisation. Merging far past "
        "a small band raises internal coordination (which grows with the "
        "square of team size) and slows local decisions, so collapse turns "
        "from great to costly."
    ),
    MoveKind.ADD_APPROVAL_LAYER: (
        "Adds a gate every team must route through. The canonical blunder: it "
        "formalises missing authority as process, so decisions slow and "
        "nothing is truly owned."
    ),
    MoveKind.SPLIT_TEAM: (
        "Divides one overloaded owner into two complete owners. It relieves "
        "load and cognitive size without adding a handoff, the opposite of "
        "splitting along a technical layer."
    ),
    MoveKind.ADD_TEAM: (
        "Stands up a fresh accountable owner to take over part of an "
        "overloaded team's load."
    ),
    MoveKind.RESOLVE_AUTHORITY: (
        "Collapses a contested decision class into a single accountable "
        "owner, so who decides never has to be settled before deciding. The "
        "great repair for matrix and dual-reporting contest."
    ),
    MoveKind.DOWNGRADE_CLAIM: (
        "Turns a claimant into a consulted party: the claim becomes an "
        "explicit dependency with a small delay, an interface rather than "
        "shared control, so the overhead is priced instead of hidden."
    ),
    MoveKind.IMPOSE_MATRIX_OVERLAY: (
        "Overlays a second claimant on every team, so every decision class "
        "becomes contested at once. The contest twin of the approval layer: "
        "dual reporting formalised as structure."
    ),
}


def move_note(kind: MoveKind) -> str:
    """A one-line structural explanation of what a move kind really does."""
    return _MOVE_NOTES[kind]


_SKEW_DECIMALS = 2
_NO_CHANGE_TEXT = "no structural field changed"
_MAX_NAMED_UNITS = 3
_UNASSIGNED_UNIT = "unassigned teams"


def _in_units(org: OrgState, teams: list) -> str:
    """Name where the change happened, matching the units the map draws."""
    names = {domain.id: domain.name for domain in org.domains}
    units = sorted(
        {
            (
                names.get(team.domain_id, _UNASSIGNED_UNIT)
                if team.domain_id is not None
                else _UNASSIGNED_UNIT
            )
            for team in teams
        }
    )
    if len(units) == 1:
        return f"in {units[0]}"
    if len(units) > _MAX_NAMED_UNITS:
        shown = ", ".join(units[:_MAX_NAMED_UNITS])
        rest = count_noun(len(units) - _MAX_NAMED_UNITS, "more unit")
        return f"in {shown} and {rest}"
    return "in " + ", ".join(units[:-1]) + f" and {units[-1]}"


def describe_position_change(before: OrgState, after: OrgState) -> str:
    """One plain line stating what concretely differs between two positions.

    Computed from the positions rather than the move, so the record can
    always state the delta even where the map's encoding cannot show it (an
    incentive realignment, or a delegation inside a division that stays
    contested throughout). Team-level changes are located by the unit they
    happened in, so the line points at the box that moved rather than at an
    organisation-wide total no box displays.
    """
    parts: list[str] = []
    before_teams = {team.id: team for team in before.teams}
    gained = [
        team
        for team in after.teams
        if team.id in before_teams
        and team.has_local_authority
        and not before_teams[team.id].has_local_authority
    ]
    lost = [
        team
        for team in after.teams
        if team.id in before_teams
        and not team.has_local_authority
        and before_teams[team.id].has_local_authority
    ]
    if gained:
        parts.append(
            f"now deciding locally: {count_noun(len(gained), 'team')} "
            f"{_in_units(after, gained)}"
        )
    if lost:
        parts.append(
            f"no longer deciding locally: {count_noun(len(lost), 'team')} "
            f"{_in_units(after, lost)}"
        )
    if len(before.teams) != len(after.teams):
        parts.append(f"teams {len(before.teams)} → {len(after.teams)}")
    if len(before.claims) != len(after.claims):
        parts.append(f"standing claims {len(before.claims)} → {len(after.claims)}")
    if len(before.dependencies) != len(after.dependencies):
        parts.append(
            f"dependencies {len(before.dependencies)} → {len(after.dependencies)}"
        )
    else:
        delay_before = sum(d.propagation_delay for d in before.dependencies)
        delay_after = sum(d.propagation_delay for d in after.dependencies)
        if delay_before != delay_after:
            parts.append(f"total propagation delay {delay_before} → {delay_after}")
    changed = [
        team
        for team in after.teams
        if team.id in before_teams
        and team.incentive_skew != before_teams[team.id].incentive_skew
    ]
    if changed:
        mean_before = sum(before_teams[t.id].incentive_skew for t in changed) / len(
            changed
        )
        mean_after = sum(t.incentive_skew for t in changed) / len(changed)
        parts.append(
            f"incentive skew realigned at {count_noun(len(changed), 'team')} "
            f"{_in_units(after, changed)}, "
            f"mean {mean_before:.{_SKEW_DECIMALS}f} → "
            f"{mean_after:.{_SKEW_DECIMALS}f}"
        )
    return "; ".join(parts) if parts else _NO_CHANGE_TEXT
