"""Pure edit operations over a plan's move sequence.

Editing a plan can invalidate later moves (a move may target a team an earlier,
now-removed move created), so alongside reorder and remove there are replay and
validation helpers: first_invalid_index finds where a sequence stops applying,
and annotate describes each move while flagging the point it breaks.
"""

from __future__ import annotations

from fulcrum.application.move_text import describe_move
from fulcrum.domain.errors import FulcrumError
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, apply_move


def without_move(moves: tuple[Move, ...], index: int) -> tuple[Move, ...]:
    """Return the moves with the one at index removed."""
    return moves[:index] + moves[index + 1 :]


def moved_up(moves: tuple[Move, ...], index: int) -> tuple[Move, ...]:
    """Swap the move at index with the one before it (no-op at the top)."""
    if index <= 0:
        return moves
    ordered = list(moves)
    ordered[index - 1], ordered[index] = ordered[index], ordered[index - 1]
    return tuple(ordered)


def moved_down(moves: tuple[Move, ...], index: int) -> tuple[Move, ...]:
    """Swap the move at index with the one after it (no-op at the bottom)."""
    if index >= len(moves) - 1:
        return moves
    ordered = list(moves)
    ordered[index], ordered[index + 1] = ordered[index + 1], ordered[index]
    return tuple(ordered)


def first_invalid_index(initial_org: OrgState, moves: tuple[Move, ...]) -> int | None:
    """Return the index of the first move that fails to apply, or None."""
    current = initial_org
    for index, move in enumerate(moves):
        try:
            current = apply_move(current, move)
        except FulcrumError:
            return index
    return None


def annotate(
    initial_org: OrgState, moves: tuple[Move, ...]
) -> tuple[tuple[str, bool], ...]:
    """Describe each move, flagging the first that breaks and those after it."""
    rows: list[tuple[str, bool]] = []
    current = initial_org
    broken = False
    for move in moves:
        if broken:
            rows.append((move.display_label(), False))
            continue
        try:
            description = describe_move(current, move)
            current = apply_move(current, move)
            rows.append((description, True))
        except FulcrumError:
            rows.append((move.display_label(), False))
            broken = True
    return tuple(rows)
