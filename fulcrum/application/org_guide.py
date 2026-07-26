"""The whole-hierarchy guide: a plan for every frame of the organisation.

The move-locality result says structural value lives in many small local
repairs invisible from the summit, so a guide scoped to one frame shows one
altitude of a many-storey problem. This builder walks the domain tree and
plans every frame: each leaf section gets a full plan in its own frame and
every aggregate frame (a non-leaf unit, and the top level as units) gets the
view from that altitude, restricted to the kinds that translate down cleanly.

Sibling leaf frames are disjoint team sets and their moves act on real teams
(a scoped stabilise thins only its frame's edges), so the leaf lines compose:
applying every leaf line to the real organisation gives an honest whole-org
before and after, which is the tree's headline. Aggregate lines are shown but
never composed; they overlap the leaf repairs beneath them by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fulcrum.application.game_session import MAX_PLAYABLE_TEAMS
from fulcrum.application.interfaces import Simulator
from fulcrum.application.planner import Guide, ImprovementPlanner
from fulcrum.domain.errors import FulcrumError
from fulcrum.domain.hierarchy import (
    AGGREGATE_MOVE_KINDS,
    TOP_LEVEL_FOCUS,
    child_domains,
    domain_has_teams,
    focused_suborg,
    has_aggregate_children,
    top_level_section,
)
from fulcrum.domain.models import Domain, OrgState
from fulcrum.domain.moves import apply_move

TOP_FRAME_LABEL = "Top level (units as actors)"
WHOLE_ORG_LABEL = "Whole organisation"
_EMPTY_SCORE = 0.0

# A progress callback receives (sections planned so far, total sections).
ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True, slots=True)
class GuideNode:
    """One frame's row in the hierarchy guide.

    frame_id is what a play translates against: None for the flat whole-org
    row, TOP_LEVEL_FOCUS for the top-level frame and a domain id for a unit.
    """

    frame_id: str | None
    label: str
    category: str
    is_leaf: bool
    playable: bool
    guide: Guide
    children: tuple[GuideNode, ...] = ()


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


def _is_leaf_frame(org: OrgState, domain: Domain) -> bool:
    """A unit plays as a leaf when no child unit beneath it holds teams."""
    return not has_aggregate_children(org, domain.id)


def _plannable_domains(org: OrgState, parent_id: str | None) -> tuple[Domain, ...]:
    return tuple(
        d for d in child_domains(org, parent_id) if domain_has_teams(org, d.id)
    )


def _count_sections(org: OrgState, parent_id: str | None) -> int:
    total = 0
    for domain in _plannable_domains(org, parent_id):
        total += 1 + _count_sections(org, domain.id)
    return total


def build_org_guide(
    org: OrgState,
    simulator: Simulator,
    allow_growth: bool = False,
    progress: ProgressCallback | None = None,
) -> OrgGuide:
    """Plan every frame of the org and compose the leaf lines into a headline."""
    builder = _Builder(org, simulator, allow_growth, progress)
    return builder.build()


class _Builder:
    """One build pass: counts sections, plans frames, reports progress."""

    def __init__(
        self,
        org: OrgState,
        simulator: Simulator,
        allow_growth: bool,
        progress: ProgressCallback | None,
    ) -> None:
        self._org = org
        self._simulator = simulator
        self._full = ImprovementPlanner(simulator, allow_growth=allow_growth)
        self._aggregate = ImprovementPlanner(simulator)
        self._progress = progress
        self._grown = allow_growth
        self._done = 0
        self._total = 0

    def build(self) -> OrgGuide:
        flat_before = self._simulator.score(self._org).value
        roots = _plannable_domains(self._org, None)
        if not roots:
            self._total = 1
            node = self._flat_node()
            nodes: tuple[GuideNode, ...] = (node,)
        else:
            self._total = 1 + _count_sections(self._org, None)
            top = self._top_frame_node()
            nodes = (top,) + tuple(self._unit_node(d) for d in roots)
        composed = compose_leaf_lines(self._org, OrgGuide(nodes, 0.0, 0.0, self._grown))
        flat_after = self._simulator.score(composed).value
        return OrgGuide(nodes, flat_before, flat_after, self._grown)

    def _tick(self) -> None:
        self._done += 1
        if self._progress is not None:
            self._progress(self._done, self._total)

    def _plan(self, section: OrgState, aggregate: bool) -> tuple[bool, Guide]:
        if len(section.teams) > MAX_PLAYABLE_TEAMS:
            self._tick()
            return False, Guide(_EMPTY_SCORE, _EMPTY_SCORE, ())
        planner = self._aggregate if aggregate else self._full
        kinds = AGGREGATE_MOVE_KINDS if aggregate else None
        guide = planner.plan(section, kinds)
        self._tick()
        return True, guide

    def _flat_node(self) -> GuideNode:
        playable, guide = self._plan(self._org, aggregate=False)
        return GuideNode(
            frame_id=None,
            label=WHOLE_ORG_LABEL,
            category="",
            is_leaf=True,
            playable=playable,
            guide=guide,
        )

    def _top_frame_node(self) -> GuideNode:
        playable, guide = self._plan(top_level_section(self._org), aggregate=True)
        return GuideNode(
            frame_id=TOP_LEVEL_FOCUS,
            label=TOP_FRAME_LABEL,
            category="",
            is_leaf=False,
            playable=playable,
            guide=guide,
        )

    def _unit_node(self, domain: Domain) -> GuideNode:
        leaf = _is_leaf_frame(self._org, domain)
        section = focused_suborg(self._org, domain.id)
        playable, guide = self._plan(section, aggregate=not leaf)
        children = tuple(
            self._unit_node(child) for child in _plannable_domains(self._org, domain.id)
        )
        return GuideNode(
            frame_id=domain.id,
            label=domain.name,
            category=domain.category,
            is_leaf=leaf,
            playable=playable,
            guide=guide,
            children=children,
        )


def compose_leaf_lines(org: OrgState, guide_tree: OrgGuide) -> OrgState:
    """The real org with every leaf line applied, in tree order.

    Leaf moves act on real teams and a scoped stabilise thins only its own
    frame's edges, so disjoint leaf lines compose without stepping on each
    other. A step that cannot replay on the real org (a grown team's
    frame-derived id landing differently there) stops that node's line and
    the rest still compose, so the headline errs conservative rather than
    failing.
    """
    current = org
    for node in guide_tree.leaf_nodes():
        for step in node.guide.steps:
            try:
                current = apply_move(current, step.move)
            except FulcrumError:
                break
    return current
