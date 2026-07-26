"""The hierarchy guide's result model: the tree of frame rows.

The builder in org_guide walks the domain tree and plans every frame; what it
returns is this model, which the guide dialog renders. The vocabulary of row
labels and synthetic frame ids lives here with it, so a consumer can name a
row without importing the builder. org_guide re-exports everything, the way
moves re-exports its vocabulary from move_base.
"""

from __future__ import annotations

from dataclasses import dataclass

from fulcrum.application.planner import Guide

TOP_FRAME_LABEL = "Top level (units as actors)"
WHOLE_ORG_LABEL = "Whole organisation"
GROWTH_FRAME_LABEL = "Growth (whole organisation)"
LOOSE_TEAMS_LABEL = "Teams directly at the top level"
LOOSE_TEAMS_FRAME = "__loose_teams__"
_DIRECT_FRAME_SUFFIX = "::direct"


def direct_teams_frame(domain_id: str) -> str:
    """The synthetic frame id of a mixed unit's direct-teams leaf row.

    It names no real unit, so a play against it translates as a pass-through
    (a focus with no child units), which is exactly right: the row's moves
    already target real teams.
    """
    return f"{domain_id}{_DIRECT_FRAME_SUFFIX}"


@dataclass(frozen=True, slots=True)
class GuideNode:
    """One frame's row in the hierarchy guide.

    frame_id is what a play translates against: None for the flat whole-org
    row, TOP_LEVEL_FOCUS for the top-level frame and a domain id for a unit.
    A direct-teams leaf row carries a synthetic id (direct_teams_frame or
    LOOSE_TEAMS_FRAME at the top level) that translates as a pass-through,
    since its moves already target real teams.
    org_delta is a leaf line's worth in whole-org points (its line applied
    alone to the real organisation), the honest number a row advertises; a
    frame's own climb is on its 0..100 scale and would overstate it.
    Aggregate rows carry no org_delta: they are views, never composed.
    grown_line marks the whole-org growth row, whose line is planned from
    the position after every leaf line, so its org_delta is growth's worth
    on top of the other lines rather than applied alone.
    composes says whether the line enters the headline: the composition
    guard drops a leaf line that would cost the whole organisation more
    than it gains once the other lines land, and compose_cost then holds
    that cost in whole-org points (zero while the line composes). The row
    stays the frame's own best line either way.
    """

    frame_id: str | None
    label: str
    category: str
    is_leaf: bool
    playable: bool
    guide: Guide
    org_delta: float = 0.0
    children: tuple[GuideNode, ...] = ()
    grown_line: bool = False
    composes: bool = True
    compose_cost: float = 0.0


@dataclass(frozen=True, slots=True)
class OrgGuide:
    """Every frame's line, plus the honest composed whole-org headline."""

    nodes: tuple[GuideNode, ...]
    flat_before: float
    flat_after: float
    grown: bool

    def leaf_nodes(self) -> tuple[GuideNode, ...]:
        """The leaf-frame rows in tree order: the lines that compose."""
        collected: list[GuideNode] = []

        def visit(node: GuideNode) -> None:
            if node.is_leaf:
                collected.append(node)
            for child in node.children:
                visit(child)

        for node in self.nodes:
            visit(node)
        return tuple(collected)
