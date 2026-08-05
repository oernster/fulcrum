"""Render an org's top-level map as a standalone SVG string for the export.

This mirrors the overview level of the on-screen map (root domains and any
unassigned teams, with aggregated dependency arrows) but emits plain SVG, so a
report stays self-contained with no Qt dependency. Every org has at least one
team, so the overview always has at least one node.
"""

from __future__ import annotations

from html import escape
from math import ceil

from fulcrum.application.map_model import build_level
from fulcrum.domain.models import OrgState
from fulcrum.shared.text import count_noun

_KIND_DOMAIN = "domain"
# The floor, not the width: a node is as wide as its own longest line needs,
# and every node on a map shares the widest so the grid stays a grid. A fixed
# width clipped its own subtitle the moment a domain had enough teams for the
# count to grow ("1,076 teams, 177 contested teams" needs half as much again).
_NODE_MIN_W = 180
_NODE_H = 72
_TEXT_INSET = 12
_LABEL_PT = 14
_SUB_PT = 12
# SVG inherits no font from a document it is embedded in when it is opened on
# its own, and the width estimate below is only meaningful against a known
# face, so the report's own stack is stated here too.
_FONT_STACK = "Segoe UI,Arial,sans-serif"
# Advance widths as a fraction of the font size. Each is the WIDEST member of
# its class measured across Segoe UI and Arial in both weights, so the total
# is an upper bound and a box is never sized under the text it holds. A table
# rather than one average, because an average wide enough for capitals leaves
# a hole after lowercase and one tuned for lowercase clips a name in capitals.
# The cost is boxes roughly a tenth wider than strictly needed, which is the
# right way to be wrong.
_NARROW_CHARS = frozenset(" .,:;'!|ijlt()[]/")
_WIDE_CHARS = frozenset("MWmw@%")
_NARROW_W = 0.39
_DIGIT_W = 0.56
_UPPER_W = 0.78
_WIDE_W = 1.02
_DEFAULT_W = 0.59
_BOLD_FACTOR = 1.15
_GAP_X = 48
_GAP_Y = 56
_MARGIN = 24
_COLS = 3
_HALF = 2
_FULL = 1.0
_AUTHORITY = (52, 211, 153)
_NO_AUTHORITY = (245, 158, 11)
# Contested ownership outranks the authority gradient: a node carrying any
# contest borders violet, matching the on-screen map.
_CONTESTED_STROKE = "#a855f7"
_DOMAIN_FILL = "#222831"
_TEAM_FILL = "#1a1e24"
_TEXT = "#e6e9ee"
_MUTED = "#9aa3af"
_EDGE = "#5b6470"
_BG = "#0d0f12"


def render_overview_svg(org: OrgState) -> str:
    """Return a self-contained SVG of the org's top-level map."""
    nodes, edges = build_level(org)
    node_w = node_width(nodes)
    positions = _positions(nodes, node_w)
    columns = min(_COLS, len(nodes))
    rows = (len(nodes) + _COLS - 1) // _COLS
    width = _MARGIN * _HALF + columns * node_w + (columns - 1) * _GAP_X
    height = _MARGIN * _HALF + rows * _NODE_H + (rows - 1) * _GAP_Y
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" '
            f'font-family="{_FONT_STACK}">'
        ),
        f'<rect width="{width}" height="{height}" fill="{_BG}"/>',
    ]
    for edge in edges:
        parts.extend(_edge_svg(edge, positions, node_w))
    for node in nodes:
        parts.extend(_node_svg(node, positions[node.id], node_w))
    parts.append("</svg>")
    return "".join(parts)


def text_width(text: str, font_size: float, *, bold: bool = False) -> float:
    """Estimate the rendered width of a string at a font size, in pixels."""
    total = 0.0
    for character in text:
        if character in _NARROW_CHARS:
            total += _NARROW_W
        elif character in _WIDE_CHARS:
            total += _WIDE_W
        elif character.isdigit():
            total += _DIGIT_W
        elif character.isupper():
            total += _UPPER_W
        else:
            total += _DEFAULT_W
    return total * font_size * (_BOLD_FACTOR if bold else 1.0)


def node_width(nodes) -> int:
    """The shared node width: wide enough for the longest line on the map."""
    widest = 0.0
    for node in nodes:
        label, sub, owner = _node_lines(node)
        widest = max(
            widest,
            text_width(label, _LABEL_PT, bold=True),
            text_width(sub, _SUB_PT),
            text_width(owner or "", _SUB_PT),
        )
    return max(_NODE_MIN_W, ceil(widest) + _TEXT_INSET * _HALF)


def _positions(nodes, node_w: int) -> dict:
    positions = {}
    for index, node in enumerate(nodes):
        row, column = divmod(index, _COLS)
        positions[node.id] = (
            _MARGIN + column * (node_w + _GAP_X),
            _MARGIN + row * (_NODE_H + _GAP_Y),
        )
    return positions


def _center(pos, node_w: int) -> tuple[float, float]:
    return pos[0] + node_w / _HALF, pos[1] + _NODE_H / _HALF


def _edge_svg(edge, positions, node_w: int) -> list[str]:
    x1, y1 = _center(positions[edge.source], node_w)
    x2, y2 = _center(positions[edge.target], node_w)
    out = [
        (
            f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
            f'stroke="{_EDGE}" stroke-width="1.5"/>'
        )
    ]
    if edge.weight > 1:
        out.append(
            f'<text x="{(x1 + x2) / _HALF:.0f}" y="{(y1 + y2) / _HALF:.0f}" '
            f'fill="{_MUTED}" font-size="12">{edge.weight}</text>'
        )
    return out


def _node_lines(node) -> tuple[str, str, str | None]:
    """The three lines a node draws: label, subtitle and owner (or None).

    The width pass and the render pass both read this, so a box can never be
    sized from text that differs from the text drawn in it.
    """
    if node.kind == _KIND_DOMAIN:
        sub = count_noun(node.team_count, "team")
        if node.contested_count:
            sub = f"{sub}, {count_noun(node.contested_count, 'contested team')}"
    elif node.contested_count:
        sub = "contested"
    else:
        sub = "decides locally" if node.authority_ratio >= _FULL else "escalates"
    owner = None
    if node.owner:
        prefix = "lead" if node.kind == _KIND_DOMAIN else "owner"
        owner = f"{prefix}: {node.owner}"
    return node.label, sub, owner


def _node_svg(node, pos, node_w: int) -> list[str]:
    x, y = pos
    fill = _DOMAIN_FILL if node.kind == _KIND_DOMAIN else _TEAM_FILL
    label, sub, owner = _node_lines(node)
    stroke = (
        _CONTESTED_STROKE if node.contested_count else _stroke(node.authority_ratio)
    )
    text_x = x + _TEXT_INSET
    parts = [
        (
            f'<rect x="{x}" y="{y}" width="{node_w}" height="{_NODE_H}" rx="10" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        ),
        (
            f'<text x="{text_x}" y="{y + 26}" fill="{_TEXT}" '
            f'font-size="{_LABEL_PT}" font-weight="bold">{escape(label)}</text>'
        ),
        (
            f'<text x="{text_x}" y="{y + 46}" fill="{_MUTED}" '
            f'font-size="{_SUB_PT}">{escape(sub)}</text>'
        ),
    ]
    if owner is not None:
        parts.append(
            f'<text x="{text_x}" y="{y + 64}" fill="{_MUTED}" '
            f'font-size="{_SUB_PT}">{escape(owner)}</text>'
        )
    return parts


def _stroke(ratio: float) -> str:
    red = int(_NO_AUTHORITY[0] + (_AUTHORITY[0] - _NO_AUTHORITY[0]) * ratio)
    green = int(_NO_AUTHORITY[1] + (_AUTHORITY[1] - _NO_AUTHORITY[1]) * ratio)
    blue = int(_NO_AUTHORITY[2] + (_AUTHORITY[2] - _NO_AUTHORITY[2]) * ratio)
    return f"#{red:02x}{green:02x}{blue:02x}"
