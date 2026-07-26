"""What the hierarchy guide says: row badges, notes and line comparison.

The dialog owns the widgets; everything worded lives here so the honesty
rules (org points in the tree, frame climbs only with their scale stated,
growth's worth on top of the other lines) sit in one place.
"""

from __future__ import annotations

from fulcrum.application.org_guide import GuideNode, OrgGuide
from fulcrum.application.planner import GuideStep
from fulcrum.shared.text import count_noun

SCORE_DECIMALS = 1
GROW_TOGGLE_TEXT = "Allow the organisation to grow (split or add teams)"
GROWTH_SAME_NOTE = "Growth does not improve any line from this position."
GROWTH_SAME_FRAME_NOTE = (
    "Growth changes nothing in this frame: no split or added owner would "
    "improve its line."
)
HINT = "Up and Down move between moves; click a move or 🔍 to preview it."
ALREADY_GOOD = (
    "This level is already in good shape; no single move improves it much " "from here."
)
AGGREGATE_NOTE = (
    "The view from this altitude: its gains overlap the leaf lines beneath "
    "it, so only leaf lines count toward the headline."
)
TOO_LARGE = "This section is too large to plan live; drill into its units."
GROWTH_TOO_LARGE = "The organisation is too large to plan growth live."
NOT_COMPOSED_BADGE = "not composed"


def step_text(index: int, step: GuideStep) -> str:
    return (
        f"{index + 1}. {step.move.display_label()}   "
        f"[{step.classification.value}]   "
        f"{step.score_before:.{SCORE_DECIMALS}f} "
        f"→ {step.score_after:.{SCORE_DECIMALS}f}"
    )


def gain(node: GuideNode) -> str:
    """The row badge: a leaf's honest worth in whole-org points.

    A frame's own climb is on its private 0..100 scale, which reads as a
    promise the whole org cannot keep, so it never appears in the tree;
    aggregate rows are views and carry no number at all.
    """
    if not node.playable:
        return "too large"
    if not node.is_leaf:
        return "view"
    if not node.guide.steps:
        return "healthy"
    if not node.composes:
        return f"{node.org_delta:+.{SCORE_DECIMALS}f} org points ({NOT_COMPOSED_BADGE})"
    return f"{node.org_delta:+.{SCORE_DECIMALS}f} org points"


def frame_climb(node: GuideNode) -> str:
    guide = node.guide
    return (
        f"{guide.start_score:.{SCORE_DECIMALS}f} → "
        f"{guide.final_score:.{SCORE_DECIMALS}f}"
    )


def frame_note_text(node: GuideNode) -> str:
    """The explanatory line under the title: frame scale, stated plainly."""
    if not node.playable or not node.guide.steps:
        return ""
    if node.grown_line:
        return (
            f"Planned from the position after every leaf line: "
            f"{frame_climb(node)} on the whole organisation's scale. The "
            "org points above are growth's worth on top of the other lines."
        )
    if node.is_leaf and not node.composes:
        return (
            f"This line scores {frame_climb(node)} on this level's own "
            "0 to 100 scale, but it does not compose into the headline: "
            "played after the other leaf lines it would cost the whole "
            f"organisation {node.compose_cost:.{SCORE_DECIMALS}f} points, "
            "since merging this level's teams raises the weight of every "
            "problem elsewhere. It is still this frame's own best line."
        )
    if node.is_leaf:
        return (
            f"This line scores {frame_climb(node)} on this level's own "
            "0 to 100 scale; its worth to the whole organisation is the "
            "org points above."
        )
    return (
        f"In this frame: {frame_climb(node)}, on its own 0 to 100 scale. "
        f"{AGGREGATE_NOTE}"
    )


def line_of(node: GuideNode) -> tuple:
    return tuple((s.move.kind, s.move.targets) for s in node.guide.steps)


def non_composing_note(tree: OrgGuide) -> str:
    """The headline's caveat when the guard left any leaf line out."""
    dropped = sum(1 for node in tree.leaf_nodes() if not node.composes)
    if not dropped:
        return ""
    return (
        f"Left out of the headline: {count_noun(dropped, 'line')} that "
        "would cost the whole organisation; see the flagged rows."
    )


def find_frame(tree: OrgGuide, frame_id: str | None) -> GuideNode | None:
    """The tree's regular row for a frame; the growth row never matches."""

    def visit(node: GuideNode) -> GuideNode | None:
        if node.frame_id == frame_id and not node.grown_line:
            return node
        for child in node.children:
            found = visit(child)
            if found is not None:
                return found
        return None

    for node in tree.nodes:
        found = visit(node)
        if found is not None:
            return found
    return None


def same_lines(first: OrgGuide, second: OrgGuide) -> bool:
    """Whether every frame's line matches, aggregate rows included: growth
    may change an aggregate line only (a split priced at the top level), and
    that must still count as growth improving a line."""

    def lines(tree: OrgGuide):
        collected = []

        def visit(node: GuideNode) -> None:
            collected.append(line_of(node))
            for child in node.children:
                visit(child)

        for node in tree.nodes:
            visit(node)
        return tuple(collected)

    return lines(first) == lines(second)
