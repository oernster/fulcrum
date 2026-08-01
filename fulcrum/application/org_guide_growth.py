"""The guide's whole-org growth line: scope, reserve and planning.

Growth (splitting a team, adding an owner) is a whole-org act: a frame
cannot price it, since a leaf drops the cross-boundary edges a split
relieves and an aggregate frame rolls teams into synthetic units. The
guide therefore plans one growth line against the real organisation after
the leaf repairs compose. This module holds that line's machinery: the
move kinds growth may use, the shortlist an oversized organisation is
scoped to, the progress reserve the build declares for the pass and the
planning of the line itself. The tree walk stays in org_guide.
"""

from __future__ import annotations

from collections.abc import Callable

from fulcrum.application.game_session import MAX_PLAYABLE_TEAMS, enumerate_moves
from fulcrum.application.interfaces import Simulator
from fulcrum.application.org_guide_model import GROWTH_FRAME_LABEL, GuideNode
from fulcrum.application.planner import ImprovementPlanner
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, MoveKind
from fulcrum.domain.simulation import coupling_of

GROWTH_MOVE_KINDS = (MoveKind.SPLIT_TEAM, MoveKind.ADD_TEAM)

# Past the live-planning size the whole-org growth line is planned over
# the most coupled teams only (growth pays where the edges live) and with
# fewer greedy steps, so the line stays live at any organisation size.
_GROWTH_SHORTLIST_TEAMS = 100
_GROWTH_LINE_MAX_STEPS = 4

# The builder's tick: work done, counted against the total it declared.
Ticker = Callable[[int], None]


def _growth_shortlist(org: OrgState) -> frozenset[str]:
    """The ids of the most coupled teams, the candidates growth considers.

    Sorted by coupling with the team id as a deterministic tiebreak, so
    the same organisation always yields the same shortlist.
    """
    ranked = sorted(
        org.teams,
        key=lambda team: (-coupling_of(org, team.id), team.id),
    )
    return frozenset(team.id for team in ranked[:_GROWTH_SHORTLIST_TEAMS])


def _growth_scope(
    simulator: Simulator, full_planner: ImprovementPlanner, org: OrgState
) -> tuple[ImprovementPlanner, frozenset[str] | None]:
    """The planner and shortlist the growth line uses at this org's size."""
    if len(org.teams) <= MAX_PLAYABLE_TEAMS:
        return full_planner, None
    planner = ImprovementPlanner(
        simulator,
        allow_growth=True,
        max_steps=_GROWTH_LINE_MAX_STEPS,
    )
    return planner, _growth_shortlist(org)


def growth_reserve(
    simulator: Simulator, full_planner: ImprovementPlanner, org: OrgState
) -> int:
    """Work units reserved for the whole-org growth pass.

    Estimated on the original organisation (the composed one the line
    actually plans over does not exist until the guard has run): the
    growth candidates it offers, valuated once per planning step, plus
    the closing tick. Growth usually stops early, so the reserve
    overshoots and the final snap closes the gap; an underestimate
    only holds the bar just short of full, it never rewinds it.
    """
    planner, shortlist = _growth_scope(simulator, full_planner, org)
    candidates = sum(
        1
        for m in enumerate_moves(org, allow_growth=True)
        if m.kind in GROWTH_MOVE_KINDS
        and (shortlist is None or shortlist.issuperset(m.targets))
    )
    return candidates * planner.max_steps + 1


def plan_growth_node(
    simulator: Simulator,
    full_planner: ImprovementPlanner,
    composed: OrgState,
    composed_score: float,
    tick: Ticker,
) -> tuple[GuideNode | None, float]:
    """The whole-org growth line, or None when growth gains nothing.

    Planned from the composed position so every remaining edge is
    visible; returns the node plus the headline including its climb.
    Past the live-planning size the line is still planned, over the
    most coupled teams only (growth pays where the edges live) and
    with fewer steps, and the node carries that scope so the guide
    states it honestly.
    """
    planner, shortlist = _growth_scope(simulator, full_planner, composed)
    keep: Callable[[Move], bool] | None = None
    if shortlist is not None:
        shortlisted = shortlist

        def keep_shortlisted(move: Move) -> bool:
            return shortlisted.issuperset(move.targets)

        keep = keep_shortlisted
    # A whole-org growth step valuates hundreds of candidates at
    # half-second whole-org scores; the planner pulses through them
    # against the reserve declared at build start. Growth usually
    # stops early, and the final snap closes the shortfall.
    guide = planner.plan(composed, GROWTH_MOVE_KINDS, keep, tick)
    tick(1)
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
        growth_shortlist=0 if shortlist is None else len(shortlist),
    )
    return node, guide.final_score
