"""The node types and pure tree helpers the org draft is built from.

These hold no draft state and no operations; they are the vocabulary the
OrgDraft in org_draft.py manipulates, split out so each module stays within
the structural line limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fulcrum.domain.models import DEFAULT_HEADCOUNT, GROUP_CATEGORIES

DEFAULT_SKEW_PERCENT = 30

# The type label offered beside the group tiers in the editor's type dropdown.
# It is not a category: choosing it converts the item to a team leaf.
TEAM_TYPE = "Team"


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


# The placeholder sequence for auto-generated names: Team Alpha, Division
# Beta and so on, wrapping to "Alpha 2" once the alphabet runs out. More
# inviting to overtype than bare numbers, while still carrying an order.
GREEK_SEQUENCE: tuple[str, ...] = (
    "Alpha",
    "Beta",
    "Gamma",
    "Delta",
    "Epsilon",
    "Zeta",
    "Eta",
    "Theta",
    "Iota",
    "Kappa",
    "Lambda",
    "Mu",
    "Nu",
    "Xi",
    "Omicron",
    "Pi",
    "Rho",
    "Sigma",
    "Tau",
    "Upsilon",
    "Phi",
    "Chi",
    "Psi",
    "Omega",
)


def sequence_token(ordinal: int) -> str:
    """The placeholder token for the nth item: Alpha ... Omega, then Alpha 2."""
    index = (ordinal - 1) % len(GREEK_SEQUENCE)
    lap = (ordinal - 1) // len(GREEK_SEQUENCE)
    name = GREEK_SEQUENCE[index]
    return name if lap == 0 else f"{name} {lap + 1}"


def _is_sequence_suffix(suffix: str) -> bool:
    """Whether a name's tail is an auto token: Greek, 'Greek n' or digits."""
    parts = suffix.split(" ")
    if parts[0] in GREEK_SEQUENCE:
        return len(parts) == 1 or (len(parts) == 2 and parts[1].isdigit())
    return suffix.isdigit()


def can_nest(child_category: str, parent_category: str) -> bool:
    """Whether a unit of child_category may sit under parent_category.

    A tier never supersedes the tiers above it: a Company cannot sit under a
    Division. Same-or-lower tiers nest freely, including skipping levels (a
    Domain directly under a Company) and repeating one (a Domain under a
    Domain). A custom label carries no tier, so it nests anywhere.
    """
    if child_category not in GROUP_CATEGORIES:
        return True
    if parent_category not in GROUP_CATEGORIES:
        return True
    child_tier = GROUP_CATEGORIES.index(child_category)
    parent_tier = GROUP_CATEGORIES.index(parent_category)
    return child_tier >= parent_tier


def retitle_for_category(name: str, old_category: str, new_category: str) -> str:
    """Re-derive an auto-generated name when its item's type changes.

    'Company Alpha' becomes 'Group Alpha' when the category drops to Group
    (numeric tails such as 'Company 3' from older models retitle too); a name
    the user has typed over is left alone.
    """
    prefix = f"{old_category} "
    if name.startswith(prefix) and _is_sequence_suffix(name[len(prefix) :]):
        return f"{new_category} {name[len(prefix):]}"
    return name


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
