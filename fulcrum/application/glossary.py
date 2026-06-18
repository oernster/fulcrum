"""The decision glossary: plain-language definitions for the in-app concepts.

It reuses the move notes and signal definitions already in the domain and adds
short, book-free explanations of the core ideas, so a player who has not read
the Decision Architecture books can still follow what each decision means.
"""

from __future__ import annotations

from fulcrum.application.move_text import move_note
from fulcrum.domain.moves import MoveKind
from fulcrum.domain.signals import SIGNAL_DEFINITIONS

_MOVES_HEADING = "Moves"
_SIGNALS_HEADING = "Signals to watch"
_CONCEPTS_HEADING = "Core ideas"

_CONCEPTS: tuple[tuple[str, str], ...] = (
    (
        "Local authority",
        "Whether a team can decide and ship on its own. With it, a real person "
        "at the team decides; without it the decision escalates to someone "
        "above, which slows delivery.",
    ),
    (
        "Escalation",
        "Pushing a decision up to higher authority because it cannot be made "
        "locally. Frequent escalation is a sign authority is missing where the "
        "work actually happens.",
    ),
    (
        "Dependency",
        "One team waiting on another before it can proceed. Each dependency is "
        "a boundary work must cross, and a place delay collects.",
    ),
    (
        "Propagation delay",
        "How long a change waits at a team boundary before the next team picks "
        "it up. Higher delay means slower flow across the organisation.",
    ),
    (
        "Domain",
        "A bounded group of teams (and sub-domains) under a lead. Domains let "
        "you navigate and reason about a large org one part at a time.",
    ),
    (
        "Incentive skew",
        "How far a team's local incentives pull against the system outcome. "
        "High skew shows up later as rework: delivered work that comes back.",
    ),
    (
        "Team size and cognitive load",
        "How large a team has grown by merging. Past a small band, internal "
        "coordination rises sharply (roughly with the square of the size) and "
        "local decisions slow, so bigger is not freely better.",
    ),
    (
        "Structural health",
        "The 0 to 100 score. It falls with backlog at boundaries (latency), "
        "with missing local authority (escalation) and with incentive skew "
        "(rework).",
    ),
    (
        "Move classification",
        "How a move scores: great or good is a clear improvement, neutral has "
        "little effect, bad or blunder makes the structure worse.",
    ),
)


def build_glossary() -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    """Return the glossary as (section heading, (term, definition) ...) groups."""
    moves = tuple((_move_term(kind), move_note(kind)) for kind in MoveKind)
    signals = tuple((d.label, d.gloss) for d in SIGNAL_DEFINITIONS)
    return (
        (_MOVES_HEADING, moves),
        (_SIGNALS_HEADING, signals),
        (_CONCEPTS_HEADING, _CONCEPTS),
    )


def _move_term(kind: MoveKind) -> str:
    return kind.value.replace("_", " ").capitalize()
