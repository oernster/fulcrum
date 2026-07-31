"""Layout for the complete picture: pure geometry, no Qt.

Sizes every node of the whole-org diagram recursively (each domain fits its
children, wrapping a few per row), decides the summary cut for very large
organisations, skips a lone wrapper tier and wraps a multi-company top
level in the synthetic Shell tier. The view draws what this lays out.
"""

from __future__ import annotations

from fulcrum.domain.hierarchy import child_domains, root_domains, teams_in_domain
from fulcrum.domain.models import Domain, OrgState

KIND_TEAM = "team"
KIND_DOMAIN = "domain"
TEAM_W = 170.0
TEAM_H = 58.0
# Four text lines: category detail, name, lead and the authority rollup.
HEADER_H = 73.0
PAD = 14.0
GAP = 16.0
PER_ROW = 3
# Root divisions stack one per row so the whole tree fills a landscape
# viewport instead of collapsing to a wide thin strip.
ROOT_COLUMNS = 1
HALF = 2.0

# Above this many teams the complete picture stops at the Division tier,
# drawing each division as one summary box (its people and team totals)
# instead of its whole subtree, so a hundred-thousand-person org reads as a
# spread of divisions rather than tens of thousands of team boxes. The teams
# are reached by drilling the navigable map instead.
SUMMARY_MAX_TEAMS = 300
SUMMARY_STOP_CATEGORY = "Division"
SUMMARY_W = 250.0
SUMMARY_H = HEADER_H + PAD

# Several root domains (a multi-company group) draw inside one synthetic
# enclosing tier labelled Shell. Presentation only: it is never part of the
# OrgState, so it cannot become a scoring roof the user did not declare and
# it is not a drill target; its dashed border marks it as unmodelled. A real
# governing tier (a Board above companies, or one within a company) is
# modelled as a unit with a custom label, which nests anywhere.
SHELL_ID = "\x00shell"
SHELL_LABEL = "Shell"
SHELL_DETAIL = "holds the top-level entities · not part of the modelled structure"


class Box:
    """A laid-out node: a team leaf, or a domain holding positioned children."""

    __slots__ = ("children", "h", "ident", "kind", "w")

    def __init__(self, kind, ident, w, h, children) -> None:
        self.kind = kind
        self.ident = ident
        self.w = w
        self.h = h
        self.children = children


def flow(
    boxes: list[Box], per_row: int = PER_ROW
) -> tuple[list[tuple[float, float, Box]], float, float]:
    """Pack boxes into rows of per_row; return (placed, width, height)."""
    placed: list[tuple[float, float, Box]] = []
    x = y = row_h = right = 0.0
    for index, box in enumerate(boxes):
        if index and index % per_row == 0:
            x = 0.0
            y += row_h + GAP
            row_h = 0.0
        placed.append((x, y, box))
        right = max(right, x + box.w)
        x += box.w + GAP
        row_h = max(row_h, box.h)
    return placed, right, y + row_h


def is_summary(domain: Domain, summarize: bool) -> bool:
    """Whether this domain draws as one summary box in a very large org."""
    return summarize and domain.category == SUMMARY_STOP_CATEGORY


def measure(org: OrgState, kind: str, ident: str, summarize: bool) -> Box:
    """Size one node and, recursively, everything inside it."""
    if kind == KIND_TEAM:
        return Box(KIND_TEAM, ident, TEAM_W, TEAM_H, [])
    domain = next(d for d in org.domains if d.id == ident)
    if is_summary(domain, summarize):
        return Box(KIND_DOMAIN, ident, SUMMARY_W, SUMMARY_H, [])
    children = [
        measure(org, KIND_DOMAIN, child.id, summarize)
        for child in child_domains(org, ident)
    ]
    children += [
        measure(org, KIND_TEAM, team.id, summarize)
        for team in teams_in_domain(org, ident, recursive=False)
    ]
    placed, inner_w, inner_h = flow(children)
    offset = [(PAD + rx, HEADER_H + ry, box) for (rx, ry, box) in placed]
    width = max(inner_w + PAD * HALF, TEAM_W + PAD * HALF)
    return Box(KIND_DOMAIN, ident, width, HEADER_H + inner_h + PAD, offset)


def _shell_box(boxes: list[Box]) -> Box:
    """The synthetic Shell tier holding every top-level entity."""
    placed, inner_w, inner_h = flow(boxes, ROOT_COLUMNS)
    offset = [(PAD + rx, HEADER_H + ry, box) for (rx, ry, box) in placed]
    width = max(inner_w + PAD * HALF, TEAM_W + PAD * HALF)
    return Box(KIND_DOMAIN, SHELL_ID, width, HEADER_H + inner_h + PAD, offset)


def skipped_wrapper_id(org: OrgState, summarize: bool) -> str | None:
    """The lone root whose wrapper box the picture skips, or None.

    A single root domain holding everything (one Company and nothing loose
    beside it) would draw as one huge box that says nothing, so the picture
    shows its contents directly; the drill map uses the same predicate so
    climbing into that root returns to the picture instead of a frame
    showing the identical tier.
    """
    roots = root_domains(org)
    loose = [t for t in org.teams if t.domain_id is None]
    if len(roots) != 1 or loose or is_summary(roots[0], summarize):
        return None
    only = roots[0]
    has_inner = bool(child_domains(org, only.id)) or bool(
        teams_in_domain(org, only.id, recursive=False)
    )
    return only.id if has_inner else None


def summarized(org: OrgState) -> bool:
    """Whether the picture draws this org at the summary cut."""
    return len(org.teams) > SUMMARY_MAX_TEAMS


def root_boxes(org: OrgState, summarize: bool) -> list[Box]:
    """The top-level layout: no lone wrapper, a Shell around several.

    Several root companies draw inside one synthetic Shell tier, so the
    collection reads as a group without asserting a modelled roof over it.
    """
    skipped = skipped_wrapper_id(org, summarize)
    if skipped is not None:
        inner = [
            measure(org, KIND_DOMAIN, domain.id, summarize)
            for domain in child_domains(org, skipped)
        ]
        inner += [
            measure(org, KIND_TEAM, team.id, summarize)
            for team in teams_in_domain(org, skipped, recursive=False)
        ]
        return inner
    roots = root_domains(org)
    loose = [t for t in org.teams if t.domain_id is None]
    boxes = [measure(org, KIND_DOMAIN, domain.id, summarize) for domain in roots]
    boxes += [measure(org, KIND_TEAM, team.id, summarize) for team in loose]
    if len(roots) > 1:
        return [_shell_box(boxes)]
    return boxes
