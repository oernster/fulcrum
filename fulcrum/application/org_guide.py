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

Growth (splitting a team, adding an owner) is a whole-org act: a frame cannot
price it, since a leaf drops the cross-boundary edges a split relieves and an
aggregate frame rolls teams into synthetic units. With growth allowed, one
extra line is planned against the real organisation after the leaf repairs
compose and appended as the tree's last leaf row, so it composes too.
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
from fulcrum.domain.moves import Move, MoveKind, apply_move

TOP_FRAME_LABEL = "Top level (units as actors)"
WHOLE_ORG_LABEL = "Whole organisation"
GROWTH_FRAME_LABEL = "Growth (whole organisation)"
_GROWTH_MOVE_KINDS = (MoveKind.SPLIT_TEAM, MoveKind.ADD_TEAM)
_EMPTY_SCORE = 0.0

# A progress callback receives (sections planned so far, total sections).
ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True, slots=True)
class GuideNode:
    """One frame's row in the hierarchy guide.

    frame_id is what a play translates against: None for the flat whole-org
    row, TOP_LEVEL_FOCUS for the top-level frame and a domain id for a unit.
    org_delta is a leaf line's worth in whole-org points (its line applied
    alone to the real organisation), the honest number a row advertises; a
    frame's own climb is on its 0..100 scale and would overstate it.
    Aggregate rows carry no org_delta: they are views, never composed.
    grown_line marks the whole-org growth row, whose line is planned from
    the position after every leaf line, so its org_delta is growth's worth
    on top of the other lines rather than applied alone.
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
        self._flat_before = 0.0

    def build(self) -> OrgGuide:
        self._flat_before = self._simulator.score(self._org).value
        roots = _plannable_domains(self._org, None)
        if not roots:
            # The flat row plans over the real org, so growth is already
            # inline in its one line; no separate growth row is needed.
            self._total = 1
            nodes: tuple[GuideNode, ...] = (self._flat_node(),)
            composed = compose_leaf_lines(
                self._org, OrgGuide(nodes, 0.0, 0.0, self._grown)
            )
            flat_after = self._simulator.score(composed).value
            return OrgGuide(nodes, self._flat_before, flat_after, self._grown)
        extra = 1 if self._grown else 0
        self._total = 1 + _count_sections(self._org, None) + extra
        top = self._top_frame_node()
        nodes = (top,) + tuple(self._unit_node(d) for d in roots)
        composed = compose_leaf_lines(self._org, OrgGuide(nodes, 0.0, 0.0, self._grown))
        flat_after = self._simulator.score(composed).value
        if self._grown:
            growth, flat_after = self._growth_node(composed, flat_after)
            if growth is not None:
                nodes = nodes + (growth,)
        return OrgGuide(nodes, self._flat_before, flat_after, self._grown)

    def _growth_node(
        self, composed: OrgState, composed_score: float
    ) -> tuple[GuideNode | None, float]:
        """The whole-org growth line, or None when growth gains nothing.

        Planned from the composed position so every remaining edge is
        visible; returns the node plus the headline including its climb.
        """
        if len(composed.teams) > MAX_PLAYABLE_TEAMS:
            self._tick()
            too_large = GuideNode(
                frame_id=None,
                label=GROWTH_FRAME_LABEL,
                category="",
                is_leaf=True,
                playable=False,
                guide=Guide(_EMPTY_SCORE, _EMPTY_SCORE, ()),
                grown_line=True,
            )
            return too_large, composed_score
        guide = self._full.plan(composed, _GROWTH_MOVE_KINDS)
        self._tick()
        if not guide.steps:
            return None, composed_score
        node = GuideNode(
            frame_id=None,
            label=GROWTH_FRAME_LABEL,
            category="",
            is_leaf=True,
            playable=True,
            guide=guide,
            org_delta=guide.final_score - guide.start_score,
            grown_line=True,
        )
        return node, guide.final_score

    def _org_delta(self, guide: Guide) -> float:
        """A leaf line's worth in whole-org points, applied alone."""
        replayed = _replay_line(self._org, guide)
        return self._simulator.score(replayed).value - self._flat_before

    def _tick(self) -> None:
        self._done += 1
        if self._progress is not None:
            self._progress(self._done, self._total)

    def _plan(self, section: OrgState, aggregate: bool) -> tuple[bool, Guide]:
        if len(section.teams) > MAX_PLAYABLE_TEAMS:
            self._tick()
            return False, Guide(_EMPTY_SCORE, _EMPTY_SCORE, ())
        if not aggregate:
            guide = self._full.plan(section)
        elif self._grown:
            # An aggregate frame is where cross-unit edges are priced, so
            # with growth allowed it may propose split or add for the real
            # teams standing in it (a loose team at the top level); rolled
            # unit nodes are synthetic and cannot grow as one act.
            guide = self._full.plan(
                section,
                AGGREGATE_MOVE_KINDS + _GROWTH_MOVE_KINDS,
                self._real_growth_only,
            )
        else:
            guide = self._aggregate.plan(section, AGGREGATE_MOVE_KINDS)
        self._tick()
        return True, guide

    def _real_growth_only(self, move: Move) -> bool:
        """Keep a growth move only when every target is a real team."""
        if move.kind not in _GROWTH_MOVE_KINDS:
            return True
        return all(self._org.has_team(target) for target in move.targets)

    def _flat_node(self) -> GuideNode:
        playable, guide = self._plan(self._org, aggregate=False)
        return GuideNode(
            frame_id=None,
            label=WHOLE_ORG_LABEL,
            category="",
            is_leaf=True,
            playable=playable,
            guide=guide,
            org_delta=self._org_delta(guide) if playable else 0.0,
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
            org_delta=self._org_delta(guide) if leaf and playable else 0.0,
            children=children,
        )


def _replay_line(org: OrgState, guide: Guide) -> OrgState:
    """org with one line applied; a step that cannot replay stops the line.

    A grown team's frame-derived id can land differently on the real org, so
    the replay errs conservative (stops that line) rather than failing.
    """
    current = org
    for step in guide.steps:
        try:
            current = apply_move(current, step.move)
        except FulcrumError:
            break
    return current


def compose_leaf_lines(org: OrgState, guide_tree: OrgGuide) -> OrgState:
    """The real org with every leaf line applied, in tree order.

    Leaf moves act on real teams and a scoped stabilise thins only its own
    frame's edges, so disjoint leaf lines compose without stepping on each
    other.
    """
    current = org
    for node in guide_tree.leaf_nodes():
        current = _replay_line(current, node.guide)
    return current
