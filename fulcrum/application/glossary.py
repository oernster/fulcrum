"""The decision glossary: plain-language definitions for the in-app concepts.

It reuses the move notes and signal definitions already in the domain and adds
short, book-free explanations of the core ideas, so a player who has not read
the Decision Architecture books can still follow what each decision means. Each
core idea also carries a short_help: the two-or-three-sentence tooltip shown
wherever the term appears in the app, so the tooltips and the glossary page
render from this one source.
"""

from __future__ import annotations

from dataclasses import dataclass

from fulcrum.application.move_text import move_note
from fulcrum.domain.moves import MoveKind
from fulcrum.domain.signals import (
    CENTRE_LOAD,
    CONTESTED,
    ESCALATIONS,
    INFLUENCE,
    QUEUE_AGE,
    REWORK_RATE,
    SIGNAL_DEFINITIONS,
    UNOWNED_INTERFACES,
)
from fulcrum.domain.simulation import DEFAULT_THRESHOLDS as _THRESHOLDS

_MOVES_HEADING = "Moves"
_SIGNALS_HEADING = "Signals to watch"
_CONCEPTS_HEADING = "Core ideas"

TERM_LOCAL_AUTHORITY = "local_authority"
TERM_ESCALATION = "escalation"
TERM_DEPENDENCY = "dependency"
TERM_PROPAGATION_DELAY = "propagation_delay"
TERM_DOMAIN = "domain"
TERM_INCENTIVE_SKEW = "incentive_skew"
TERM_TEAM_SIZE = "team_size"
TERM_STRUCTURAL_HEALTH = "structural_health"
TERM_MOVE_CLASSIFICATION = "move_classification"
TERM_WORKLOAD = "workload"
TERM_AUTHORITY_CLAIM = "authority_claim"
TERM_PRINCE_BAND = "prince_band"
TERM_RESOLUTION_NEIGHBOURHOOD = "resolution_neighbourhood"
TERM_UNOWNED_INTERFACE = "unowned_interface"


@dataclass(frozen=True, slots=True)
class ConceptEntry:
    """One core idea: its display term, long definition and tooltip text."""

    key: str
    term: str
    definition: str
    short_help: str


_CONCEPTS: tuple[ConceptEntry, ...] = (
    ConceptEntry(
        key=TERM_LOCAL_AUTHORITY,
        term="Local authority",
        definition=(
            "Whether a team can decide and ship on its own. With it, a real "
            "person at the team decides; without it the decision escalates to "
            "someone above, which slows delivery."
        ),
        short_help=(
            "Whether this team can decide and ship on its own. A team that "
            "must ask a committee before every release does not ship without "
            "asking; a team that deploys on its own decision does."
        ),
    ),
    ConceptEntry(
        key=TERM_ESCALATION,
        term="Escalation",
        definition=(
            "Pushing a decision up to higher authority because it cannot be "
            "made locally. Frequent escalation is a sign authority is missing "
            "where the work actually happens."
        ),
        short_help=(
            "A decision pushed up because it cannot be made locally. A team "
            "that needs sign-off for every schema change escalates "
            "constantly; that wait is structural, not personal."
        ),
    ),
    ConceptEntry(
        key=TERM_DEPENDENCY,
        term="Dependency",
        definition=(
            "One item waiting on another before it can proceed: team on "
            "team, unit on unit or across levels (a division blocked on a "
            "single platform team). Each dependency is a boundary work must "
            "cross, and a place delay collects; a unit-level dependency "
            "counts in the frames where both its endpoints appear as nodes."
        ),
        short_help=(
            "One item waiting on another before it can proceed; either side "
            "can be a team or a whole unit. If Mobile cannot release until "
            "Platform publishes an API, Mobile is downstream of Platform "
            "and every handoff collects delay."
        ),
    ),
    ConceptEntry(
        key=TERM_PROPAGATION_DELAY,
        term="Propagation delay",
        definition=(
            "How long a change waits at a team boundary before the next team "
            "picks it up. Higher delay means slower flow across the "
            "organisation."
        ),
        short_help=(
            "How many turns a change waits at a boundary before the next "
            "team picks it up. A ticket that sits four days in another "
            "team's queue is four days of propagation delay."
        ),
    ),
    ConceptEntry(
        key=TERM_DOMAIN,
        term="Domain",
        definition=(
            "A bounded group of teams (and sub-domains) under a lead. Domains "
            "let you navigate and reason about a large org one part at a "
            "time."
        ),
        short_help=(
            "A bounded group of teams and sub-groups under one lead, such as "
            "a division or department. The map lets you drill into one "
            "domain and play it as its own section."
        ),
    ),
    ConceptEntry(
        key=TERM_INCENTIVE_SKEW,
        term="Incentive skew",
        definition=(
            "How far a team's local incentives pull against the system "
            "outcome. High skew shows up later as rework: delivered work that "
            "comes back."
        ),
        short_help=(
            "How far this team's rewards pull away from the outcomes it is "
            "asked to ship. A team measured on tickets closed while asked to "
            "improve reliability has high skew."
        ),
    ),
    ConceptEntry(
        key=TERM_TEAM_SIZE,
        term="Team size and cognitive load",
        definition=(
            "How large a team has grown by merging. Past a small band, "
            "internal coordination rises sharply (roughly with the square of "
            "the size) and local decisions slow, so bigger is not freely "
            "better."
        ),
        short_help=(
            "How large a unit has grown by merging teams. Past a small band "
            "its internal coordination cost rises sharply, so collapsing "
            "every boundary into one huge team stops paying."
        ),
    ),
    ConceptEntry(
        key=TERM_STRUCTURAL_HEALTH,
        term="Structural health",
        definition=(
            "The 0 to 100 score. It falls with backlog at boundaries "
            "(latency), with missing local authority (escalation) and with "
            "incentive skew (rework)."
        ),
        short_help=(
            "The 0 to 100 score for the structure being viewed. It falls "
            "with backlog at boundaries, with teams that cannot decide "
            "locally and with skewed incentives."
        ),
    ),
    ConceptEntry(
        key=TERM_MOVE_CLASSIFICATION,
        term="Move classification",
        definition=(
            "How a move scores, by the points it would add to or remove from "
            f"the structural health score: great adds "
            f"{_THRESHOLDS.great_delta:g} or more, good adds "
            f"{_THRESHOLDS.good_delta:g} or more, neutral gains less than "
            f"{_THRESHOLDS.good_delta:g} without losing anything, bad loses "
            f"less than {-_THRESHOLDS.blunder_delta:g} and blunder loses "
            f"{-_THRESHOLDS.blunder_delta:g} or more. Deltas are scored "
            "within the focused section, so the same change reads larger the "
            "deeper the focus; when nothing at an aggregate level grades "
            "good, the value lives in the sections beneath it."
        ),
        short_help=(
            "How a move scores before you play it, exactly as a chess engine "
            f"grades moves: great adds {_THRESHOLDS.great_delta:g} or more "
            f"points, good at least {_THRESHOLDS.good_delta:g}, neutral "
            f"gains less than {_THRESHOLDS.good_delta:g}, bad dips below "
            f"zero and blunder loses {-_THRESHOLDS.blunder_delta:g} or more."
        ),
    ),
    ConceptEntry(
        key=TERM_AUTHORITY_CLAIM,
        term="Authority claim and contested ownership",
        definition=(
            "A claim is another actor asserting the right to decide for a "
            "team: a second reporting line, a functional chapter, a matrix "
            "overlay. Every decision class already has a structural owner "
            "(the team itself, or the line it escalates to), so any standing "
            "claim makes the team contested: who decides must be settled "
            "before anything can be decided, which is slower than clean "
            "escalation and produces conflicting decisions."
        ),
        short_help=(
            "Another actor asserting the right to decide for this team. The "
            "structural owner is already one claimant, so any standing claim "
            "is a contest and every decision starts with an argument about "
            "who decides."
        ),
    ),
    ConceptEntry(
        key=TERM_PRINCE_BAND,
        term="The prince band and the Dunbar horizon",
        definition=(
            "Concentrated authority is priced by scale. Up to about 150 "
            "people (the Dunbar horizon) one decisive founder works: "
            "escalating to them is a conversation, so concentration costs "
            "little. From 150 to 200 the price rises to its full rate, and "
            "beyond that it grows with the size of the organisation, capped "
            "so that the rare founder who scales command is penalised, "
            "never ruled out. Machiavelli both ways: the Prince for the "
            "small state, the republic for the large one."
        ),
        short_help=(
            "Concentration priced by size. A 30-person company run by one "
            "decisive founder scores well; the identical structure at 3,000 "
            "people scores badly, because the centre is now far from the "
            "work."
        ),
    ),
    ConceptEntry(
        key=TERM_RESOLUTION_NEIGHBOURHOOD,
        term="Resolution neighbourhood and escalation load",
        definition=(
            "Where a team's escalations actually resolve: the nearest "
            "enclosing unit holding someone with authority. Escalation is "
            "priced at that unit's size, so a team whose lead sits across "
            "the desk is never priced as if it escalated to a conglomerate "
            "summit. A share of each escalating team's work also lands on "
            "the resolving authority's own queue, so a centre absorbing "
            "thirty teams' escalations visibly saturates."
        ),
        short_help=(
            "The nearest enclosing unit where this team's escalations "
            "resolve. Escalating one desk over is cheap at any company "
            "size; the resolving lead carries the escalated load on their "
            "own queue."
        ),
    ),
    ConceptEntry(
        key=TERM_UNOWNED_INTERFACE,
        term="Unowned interface",
        definition=(
            "A dependency between two teams that both hold authority but "
            "share no working roof: no common unit containing a further "
            "authority who could arbitrate a conflict on that edge. Two "
            "founders across a desk resolve it by talking, so it is cheap "
            "when small; at scale it is fragmentation, decisions made "
            "locally that conflict globally with nowhere to settle them."
        ),
        short_help=(
            "Two sovereign teams depending on each other with nobody above "
            "both to settle a conflict. Fine between founders, "
            "fragmentation at scale."
        ),
    ),
    ConceptEntry(
        key=TERM_WORKLOAD,
        term="Workload",
        definition=(
            "The number of decisions arriving at each team every turn. Higher "
            "workload fills queues faster, so the same structure scores worse "
            "under more pressure."
        ),
        short_help=(
            "Decisions arriving at each team every turn. Six means a steady "
            "stream of calls to make; raising it fills queues faster and "
            "exposes weak structure sooner."
        ),
    ),
)

# Tooltip text for the signal chips, keyed by the signal's domain key and
# written in the same register as the concept short_helps: plain sentences
# with one concrete example.
_SIGNAL_SHORT_HELP: dict[str, str] = {
    QUEUE_AGE: (
        "How long work waits at team boundaries before the next team picks "
        "it up. A pull request that sits three days awaiting another team's "
        "review is aging in a handoff queue."
    ),
    ESCALATIONS: (
        "How many teams must push decisions up to ship a release. A release "
        "that needs two board approvals and a director's sign-off scores "
        "three escalations."
    ),
    REWORK_RATE: (
        "The share of delivered work that comes back for redo. A feature "
        "shipped to hit a date then rebuilt next quarter is rework; skewed "
        "incentives raise it."
    ),
    INFLUENCE: (
        "Load on teams that many others depend on but that cannot decide "
        "locally. A platform team everyone waits on but that cannot approve "
        "its own changes carries this load and it burns people out."
    ),
    CONTESTED: (
        "Teams whose decisions have more than one claimant, the matrix "
        "disease. A team answering to both a line manager and a chapter "
        "lead settles who decides before it can decide anything."
    ),
    CENTRE_LOAD: (
        "Escalated decisions per turn landing on the most loaded authority. "
        "A founder personally deciding for thirty teams carries a queue "
        "that grows faster than any one person can clear."
    ),
    UNOWNED_INTERFACES: (
        "Dependencies between two sovereign teams with nobody above both "
        "to settle a conflict. Two founders talk it out; two hundred "
        "autonomous teams with no shared institutions fragment."
    ),
}

_SHORT_HELP: dict[str, str] = {
    **{entry.key: entry.short_help for entry in _CONCEPTS},
    **_SIGNAL_SHORT_HELP,
}


def short_help(key: str) -> str:
    """The tooltip text for a concept or signal key; raises on an unknown key."""
    return _SHORT_HELP[key]


def build_glossary() -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    """Return the glossary as (section heading, (term, definition) ...) groups."""
    moves = tuple((_move_term(kind), move_note(kind)) for kind in MoveKind)
    signals = tuple((d.label, d.gloss) for d in SIGNAL_DEFINITIONS)
    concepts = tuple((entry.term, entry.definition) for entry in _CONCEPTS)
    return (
        (_MOVES_HEADING, moves),
        (_SIGNALS_HEADING, signals),
        (_CONCEPTS_HEADING, concepts),
    )


def _move_term(kind: MoveKind) -> str:
    return kind.value.replace("_", " ").capitalize()
