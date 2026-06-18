"""Human-readable descriptions of moves, using team names for context.

Two delegate moves or two collapse moves are only distinguishable by who they
act on, so the board needs the team names, not just the move kind.
"""

from __future__ import annotations

from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, MoveKind

_STABILISE_TEXT = "Stabilise all interfaces"
_APPROVAL_TEXT = "Add an approval layer"


def _named(org: OrgState, ids: tuple[str, ...]) -> str:
    return " + ".join(org.team(team_id).name for team_id in ids)


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
}


def move_note(kind: MoveKind) -> str:
    """A one-line structural explanation of what a move kind really does."""
    return _MOVE_NOTES[kind]
