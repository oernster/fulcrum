"""The node types and pure tree helpers the org draft is built from.

These hold no draft state and no operations; they are the vocabulary the
OrgDraft in org_draft.py manipulates, split out so each module stays within
the structural line limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fulcrum.domain.models import DEFAULT_HEADCOUNT, GROUP_CATEGORIES

DEFAULT_SKEW_PERCENT = 30


@dataclass
class TeamDraft:
    """A team leaf while it is being edited."""

    id: str
    name: str
    people: int = DEFAULT_HEADCOUNT
    ships_without_asking: bool = False
    skew_percent: int = DEFAULT_SKEW_PERCENT
    owner: str = ""
    size: int = 1


@dataclass
class ContainerDraft:
    """A grouping (Company, Division, ...) while it is being edited.

    unit_headcount is a pass-through: some imported units carry their own
    population rather than counting people through teams. The editor does not
    edit it but must not lose it on a round trip.
    """

    id: str
    category: str
    name: str
    lead: str = ""
    children: list = field(default_factory=list)
    unit_headcount: int = 0


@dataclass(frozen=True, slots=True)
class RemovalSummary:
    """What a removal would take with it, for the confirmation text."""

    name: str
    is_container: bool
    team_count: int
    people: int


@dataclass(frozen=True, slots=True)
class DraftWarning:
    """A non-blocking problem, anchored to the node it concerns."""

    node_id: str
    message: str


def default_category_for_depth(depth: int) -> str:
    """The group tier suggested at a nesting depth: Company down to Domain."""
    return GROUP_CATEGORIES[min(depth, len(GROUP_CATEGORIES) - 1)]


def iter_nodes(siblings: list):
    """Every node in tree order: each sibling then its subtree."""
    for node in siblings:
        yield node
        if isinstance(node, ContainerDraft):
            yield from iter_nodes(node.children)


def subtree(node) -> list:
    """The node and everything beneath it, in tree order."""
    if isinstance(node, ContainerDraft):
        return [node, *(n for child in node.children for n in subtree(child))]
    return [node]


def teams_beneath(node) -> list[TeamDraft]:
    """The team leaves within a node's subtree, itself included if a team."""
    return [n for n in subtree(node) if isinstance(n, TeamDraft)]
