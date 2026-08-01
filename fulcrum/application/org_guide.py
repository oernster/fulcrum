"""The whole-hierarchy guide: a plan for every frame of the organisation.

The move-locality result says structural value lives in many small local
repairs invisible from the summit, so a guide scoped to one frame shows one
altitude of a many-storey problem. This builder walks the domain tree and
plans every frame: each leaf section gets a full plan in its own frame and
every aggregate frame (a non-leaf unit) gets the view from that altitude,
restricted to the kinds that translate down cleanly. The top-level frame
gets no row: no authority sits above the top level to make a move there.

Sibling leaf frames are disjoint team sets and their moves act on real teams
(a scoped stabilise thins only its frame's edges), so the leaf lines compose:
applying every leaf line to the real organisation gives an honest whole-org
before and after, which is the tree's headline. Composition is guarded: a
leaf line that would cost the whole organisation once the other lines land
(a frame cannot see the per-team means its collapses dilute elsewhere) is
marked as not composing and left out of the headline, its row saying why
(see org_guide_compose). Aggregate lines are shown but never composed; they
overlap the leaf repairs beneath them by construction.
A mixed unit (teams held directly beside child units that hold teams) gets an
extra leaf row for its direct teams, as does the top level for loose teams,
so every team sits in exactly one leaf frame and no repair is dropped from
the headline.

Growth (splitting a team, adding an owner) is a whole-org act: a frame cannot
price it, since a leaf drops the cross-boundary edges a split relieves and an
aggregate frame rolls teams into synthetic units. With growth allowed, one
extra line is planned against the real organisation after the leaf repairs
compose and appended as the tree's last leaf row, so it composes too.

The result model (GuideNode, OrgGuide) and the row vocabulary live in
org_guide_model and are re-exported here, so callers import everything from
this module.
"""

from __future__ import annotations

from collections.abc import Callable

from fulcrum.application.game_session import MAX_PLAYABLE_TEAMS
from fulcrum.application.interfaces import Simulator
from fulcrum.application.org_guide_compose import (
    compose_leaf_lines,
    guard_leaf_lines,
    replay_line,
)
from fulcrum.application.org_guide_growth import (
    GROWTH_MOVE_KINDS,
    growth_reserve,
    plan_growth_node,
)
from fulcrum.application.org_guide_model import (
    LOOSE_TEAMS_FRAME,
    LOOSE_TEAMS_LABEL,
    WHOLE_ORG_LABEL,
    GuideNode,
    OrgGuide,
    direct_teams_frame,
)
from fulcrum.application.planner import Guide, ImprovementPlanner
from fulcrum.domain.hierarchy import (
    AGGREGATE_MOVE_KINDS,
    child_domains,
    direct_teams_section,
    domain_has_teams,
    focused_suborg,
    has_aggregate_children,
    has_direct_teams,
)
from fulcrum.domain.models import Domain, OrgState
from fulcrum.domain.moves import Move

_EMPTY_SCORE = 0.0


# A progress callback receives (work done, total work). Work units cover
# every long phase: one per section planned, one per line the composition
# guard prices and one per candidate a whole-org growth step valuates, so
# the bar moves for the whole build, not only while sections plan. The
# total is declared once, up front, from reserves that bound the open-ended
# phases, so the reported fraction never decreases: a phase that overruns
# its reserve holds the bar just short of full instead of growing the
# total, and only the final snap reports complete.
ProgressCallback = Callable[[int, int], None]


def _is_leaf_frame(org: OrgState, domain: Domain) -> bool:
    """A unit plays as a leaf when no child unit beneath it holds teams."""
    return not has_aggregate_children(org, domain.id)


def _plannable_domains(org: OrgState, parent_id: str | None) -> tuple[Domain, ...]:
    return tuple(
        d for d in child_domains(org, parent_id) if domain_has_teams(org, d.id)
    )


def _needs_direct_row(org: OrgState, domain: Domain) -> bool:
    """Whether a unit is mixed: an aggregate frame holding teams directly.

    Its direct teams sit in no child unit's frame, so without a leaf row of
    their own their repairs would never compose into the headline.
    """
    return not _is_leaf_frame(org, domain) and has_direct_teams(org, domain.id)


def _count_sections(org: OrgState, parent_id: str | None) -> int:
    total = 0
    for domain in _plannable_domains(org, parent_id):
        total += 1 + _count_sections(org, domain.id)
        if _needs_direct_row(org, domain):
            total += 1
    return total


def _count_leaf_frames(org: OrgState, parent_id: str | None) -> int:
    """How many leaf rows the tree will hold, before any is planned.

    An upper bound on the lines the composition guard prices (a line must
    also compose and hold steps), so it serves as the guard's progress
    reserve: known before planning starts, never undershooting one pass.
    """
    total = 0
    for domain in _plannable_domains(org, parent_id):
        if _is_leaf_frame(org, domain):
            total += 1
        else:
            total += _count_leaf_frames(org, domain.id)
            if _needs_direct_row(org, domain):
                total += 1
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
        self._finished = False
        self._flat_before = 0.0

    def build(self) -> OrgGuide:
        self._flat_before = self._simulator.score(self._org).value
        roots = _plannable_domains(self._org, None)
        if not roots:
            # The flat row plans over the real org, so growth is already
            # inline in its one line and no separate growth row is needed.
            # Every step of that line gains at the org level by planner
            # construction, so the composition guard has nothing to price.
            self._total = 1
            nodes: tuple[GuideNode, ...] = (self._flat_node(),)
            composed = compose_leaf_lines(
                self._org, OrgGuide(nodes, 0.0, 0.0, self._grown)
            )
            flat_after = self._simulator.score(composed).value
            self._finish()
            return OrgGuide(nodes, self._flat_before, flat_after, self._grown)
        # The whole build's total, declared before any work: the exact
        # section count, a guard reserve (the guard prices every composing
        # leaf line against the whole org, most of the build on a large
        # organisation, bounded by the leaf-row count) and a growth reserve
        # estimated from the original organisation. A single up-front total
        # is what keeps the bar monotone: extending it mid-build would drop
        # the reported fraction back after it had climbed.
        loose = 1 if has_direct_teams(self._org, None) else 0
        sections = loose + _count_sections(self._org, None)
        guard_reserve = loose + _count_leaf_frames(self._org, None)
        growth = (
            growth_reserve(self._simulator, self._full, self._org) if self._grown else 0
        )
        self._total = sections + guard_reserve + growth
        nodes: tuple[GuideNode, ...] = ()
        if loose:
            nodes = nodes + (
                self._direct_node(None, LOOSE_TEAMS_LABEL, LOOSE_TEAMS_FRAME),
            )
        nodes = nodes + tuple(self._unit_node(d) for d in roots)
        nodes, composed = guard_leaf_lines(
            self._org, self._simulator, nodes, self._pulse
        )
        flat_after = self._simulator.score(composed).value
        if self._grown:
            node, flat_after = plan_growth_node(
                self._simulator, self._full, composed, flat_after, self._tick
            )
            if node is not None:
                nodes = nodes + (node,)
        self._finish()
        return OrgGuide(nodes, self._flat_before, flat_after, self._grown)

    def _org_delta(self, guide: Guide) -> float:
        """A leaf line's worth in whole-org points, applied alone."""
        replayed = replay_line(self._org, guide)
        return self._simulator.score(replayed).value - self._flat_before

    def _tick(self, count: int = 1) -> None:
        self._done += count
        self._report()

    def _pulse(self) -> None:
        self._tick()

    def _finish(self) -> None:
        self._finished = True
        self._total = self._done
        self._report()

    def _report(self) -> None:
        if self._progress is None:
            return
        # The reported fraction is monotone: work is clamped just short
        # of the declared total until the build finishes, so a phase that
        # overruns its reserve holds the bar steady instead of refilling
        # it, and only the final snap reports complete.
        done = self._done if self._finished else min(self._done, self._total - 1)
        self._progress(done, self._total)

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
                AGGREGATE_MOVE_KINDS + GROWTH_MOVE_KINDS,
                self._real_growth_only,
            )
        else:
            guide = self._aggregate.plan(section, AGGREGATE_MOVE_KINDS)
        self._tick()
        return True, guide

    def _real_growth_only(self, move: Move) -> bool:
        """Keep a growth move only when every target is a real team."""
        if move.kind not in GROWTH_MOVE_KINDS:
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

    def _direct_node(
        self, parent_id: str | None, label: str, frame_id: str
    ) -> GuideNode:
        """A leaf row for the teams a mixed parent holds directly.

        Those teams stand in the parent's aggregate frame; aggregate
        lines never compose, so this row is where their repairs count.
        """
        playable, guide = self._plan(
            direct_teams_section(self._org, parent_id), aggregate=False
        )
        return GuideNode(
            frame_id=frame_id,
            label=label,
            category="",
            is_leaf=True,
            playable=playable,
            guide=guide,
            org_delta=self._org_delta(guide) if playable else 0.0,
        )

    def _unit_node(self, domain: Domain) -> GuideNode:
        leaf = _is_leaf_frame(self._org, domain)
        section = focused_suborg(self._org, domain.id)
        playable, guide = self._plan(section, aggregate=not leaf)
        children: tuple[GuideNode, ...] = ()
        if _needs_direct_row(self._org, domain):
            children = (
                self._direct_node(
                    domain.id,
                    f"Teams directly in {domain.name}",
                    direct_teams_frame(domain.id),
                ),
            )
        children = children + tuple(
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
