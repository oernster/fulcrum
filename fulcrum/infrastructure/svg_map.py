"""Render an org's top-level map as a standalone SVG string for the export.

This mirrors the overview level of the on-screen map (root domains and any
unassigned teams, with aggregated dependency arrows) but emits plain SVG, so a
report stays self-contained with no Qt dependency. Every org has at least one
team, so the overview always has at least one node.
"""

from __future__ import annotations

from html import escape

from fulcrum.application.map_model import build_level
from fulcrum.domain.models import OrgState
from fulcrum.shared.text import count_noun

_KIND_DOMAIN = "domain"
_NODE_W = 180
_NODE_H = 72
_GAP_X = 48
_GAP_Y = 56
_MARGIN = 24
_COLS = 3
_HALF = 2
_FULL = 1.0
_AUTHORITY = (52, 211, 153)
_NO_AUTHORITY = (245, 158, 11)
_DOMAIN_FILL = "#222831"
_TEAM_FILL = "#1a1e24"
_TEXT = "#e6e9ee"
_MUTED = "#9aa3af"
_EDGE = "#5b6470"
_BG = "#0d0f12"


def render_overview_svg(org: OrgState) -> str:
    """Return a self-contained SVG of the org's top-level map."""
    nodes, edges = build_level(org)
    positions = _positions(nodes)
    columns = min(_COLS, len(nodes))
    rows = (len(nodes) + _COLS - 1) // _COLS
    width = _MARGIN * _HALF + columns * _NODE_W + (columns - 1) * _GAP_X
    height = _MARGIN * _HALF + rows * _NODE_H + (rows - 1) * _GAP_Y
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{_BG}"/>',
    ]
    for edge in edges:
        parts.extend(_edge_svg(edge, positions))
    for node in nodes:
        parts.extend(_node_svg(node, positions[node.id]))
    parts.append("</svg>")
    return "".join(parts)


def _positions(nodes) -> dict:
    positions = {}
    for index, node in enumerate(nodes):
        row, column = divmod(index, _COLS)
        positions[node.id] = (
            _MARGIN + column * (_NODE_W + _GAP_X),
            _MARGIN + row * (_NODE_H + _GAP_Y),
        )
    return positions


def _center(pos) -> tuple[float, float]:
    return pos[0] + _NODE_W / _HALF, pos[1] + _NODE_H / _HALF


def _edge_svg(edge, positions) -> list[str]:
    x1, y1 = _center(positions[edge.source])
    x2, y2 = _center(positions[edge.target])
    out = [
        f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
        f'stroke="{_EDGE}" stroke-width="1.5"/>'
    ]
    if edge.weight > 1:
        out.append(
            f'<text x="{(x1 + x2) / _HALF:.0f}" y="{(y1 + y2) / _HALF:.0f}" '
            f'fill="{_MUTED}" font-size="12">{edge.weight}</text>'
        )
    return out


def _node_svg(node, pos) -> list[str]:
    x, y = pos
    fill = _DOMAIN_FILL if node.kind == _KIND_DOMAIN else _TEAM_FILL
    if node.kind == _KIND_DOMAIN:
        sub = count_noun(node.team_count, "team")
    else:
        sub = "decides locally" if node.authority_ratio >= _FULL else "escalates"
    parts = [
        f'<rect x="{x}" y="{y}" width="{_NODE_W}" height="{_NODE_H}" rx="10" '
        f'fill="{fill}" stroke="{_stroke(node.authority_ratio)}" stroke-width="2"/>',
        f'<text x="{x + 12}" y="{y + 26}" fill="{_TEXT}" font-size="14" '
        f'font-weight="bold">{escape(node.label)}</text>',
        f'<text x="{x + 12}" y="{y + 46}" fill="{_MUTED}" '
        f'font-size="12">{escape(sub)}</text>',
    ]
    if node.owner:
        prefix = "lead" if node.kind == _KIND_DOMAIN else "owner"
        parts.append(
            f'<text x="{x + 12}" y="{y + 64}" fill="{_MUTED}" '
            f'font-size="12">{prefix}: {escape(node.owner)}</text>'
        )
    return parts


def _stroke(ratio: float) -> str:
    red = int(_NO_AUTHORITY[0] + (_AUTHORITY[0] - _NO_AUTHORITY[0]) * ratio)
    green = int(_NO_AUTHORITY[1] + (_AUTHORITY[1] - _NO_AUTHORITY[1]) * ratio)
    blue = int(_NO_AUTHORITY[2] + (_AUTHORITY[2] - _NO_AUTHORITY[2]) * ratio)
    return f"#{red:02x}{green:02x}{blue:02x}"
