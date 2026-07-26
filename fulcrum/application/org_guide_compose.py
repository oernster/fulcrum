"""Leaf-line composition, guarded so the headline never recommends net harm.

A leaf line is planned inside its own frame, which cannot see the rest of the
organisation. The whole-org score carries per-team means (the escalation
share, the rework mean, the latency ratio), so a line that reads clean on its
frame's scale (collapsing healthy teams) can still cost the whole organisation
by raising the weight of every problem elsewhere: the app's own observer
relativity, biting its recommendation surface. Applied-alone worth (the
org_delta badge) does not decide it either way: once the sibling lines repair
their own frames the same line can turn positive, so dropping lines by badge
sign would cost the headline real points. The guard therefore prices each
line marginally against the composed position and drops the worst net-harmful
line, repeating until every surviving line pays its way; a dropped line keeps
its row and badge, marked as not composing with its cost.
"""

from __future__ import annotations

from dataclasses import replace

from fulcrum.application.interfaces import Simulator
from fulcrum.application.org_guide_model import GuideNode, OrgGuide
from fulcrum.application.planner import Guide
from fulcrum.domain.errors import FulcrumError
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import apply_move

_NO_COST = 0.0


def replay_line(org: OrgState, guide: Guide) -> OrgState:
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
    """The real org with every composing leaf line applied, in tree order.

    Leaf moves act on real teams and a scoped stabilise thins only its own
    frame's edges, so disjoint leaf lines compose without stepping on each
    other. A line the guard marked as not composing is skipped: it remains
    its frame's best line but would cost the whole organisation.
    """
    current = org
    for node in guide_tree.leaf_nodes():
        if node.composes:
            current = replay_line(current, node.guide)
    return current


def guard_leaf_lines(
    org: OrgState, simulator: Simulator, nodes: tuple[GuideNode, ...]
) -> tuple[tuple[GuideNode, ...], OrgState]:
    """Drop net-harmful leaf lines; return the marked tree and composed org.

    Each pass composes the surviving lines, prices every line marginally
    (the headline with it minus the headline without it) and marks the
    single worst negative line as not composing, then reprices: marginals
    interact, so lines are dropped one at a time, worst first, and the
    order is deterministic. The loop ends when every survivor helps.
    """
    while True:
        tree = OrgGuide(nodes, _NO_COST, _NO_COST, False)
        lines = tuple(n for n in tree.leaf_nodes() if n.composes and n.guide.steps)
        composed = compose_leaf_lines(org, tree)
        full = simulator.score(composed).value
        worst: GuideNode | None = None
        worst_marginal = _NO_COST
        for line in lines:
            marginal = full - simulator.score(_without(org, lines, line)).value
            if marginal < worst_marginal:
                worst, worst_marginal = line, marginal
        if worst is None:
            return nodes, composed
        nodes = _mark_non_composing(nodes, worst, -worst_marginal)


def _without(
    org: OrgState, lines: tuple[GuideNode, ...], skipped: GuideNode
) -> OrgState:
    """The composed org with every line but one applied, in tree order."""
    current = org
    for node in lines:
        if node is not skipped:
            current = replay_line(current, node.guide)
    return current


def _mark_non_composing(
    nodes: tuple[GuideNode, ...], target: GuideNode, cost: float
) -> tuple[GuideNode, ...]:
    """The tree with one node marked as not composing, rebuilt on the path."""

    def visit(node: GuideNode) -> GuideNode:
        children = tuple(visit(child) for child in node.children)
        if node is target:
            return replace(node, children=children, composes=False, compose_cost=cost)
        if any(new is not old for new, old in zip(children, node.children)):
            return replace(node, children=children)
        return node

    return tuple(visit(node) for node in nodes)
