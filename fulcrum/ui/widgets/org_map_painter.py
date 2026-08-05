"""Pure scene painting for the org map: nodes, edges and the back breadcrumb.

Kept apart from OrgMapView so the view holds only navigation, hit-testing and the
hover, change and cursor overlays, staying within the module-size limit. Every
function draws into a QGraphicsScene and reads nothing but its arguments.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QGraphicsScene

from fulcrum.shared.text import count_noun
from fulcrum.ui.map_palette import map_palette
from fulcrum.ui.widgets.map_geometry import arrow_head, edge_span

KIND_DOMAIN = "domain"
NODE_W = 240.0
NODE_H = 88.0
CORNER = 10.0
# The action ring sits outside a node's own border; the view's fit margin
# derives from these so a ringed edge node is never clipped.
RING_INSET = 5.0
RING_PEN = 3.0

# Contested ownership outranks the authority gradient: any contest reads
# violet (never red, which would read as an error and collide with the green
# hover ring for red-green colour-blind readers).

_GAP_Y = 72.0
_PAD = 12.0
_SUB_DROP = 24.0
_SUB_LINE2 = 42.0
_ARROW = 11.0
_HALF = 2.0
_FULL = 1.0
_PERSON_X = 26.0
_PERSON_TOP = 14.0
_HEAD_R = 5.0
_BODY_LEN = 20.0
_ARM_Y = 13.0
_ARM = 8.0
_LEG = 6.0
_LEG_DROP = 9.0
_ESCALATE = "↑"

# Text is elided to the inner width so a long label never spills the node; the
# label row also leaves room for the person glyph on the right.
_LABEL_WIDTH = NODE_W - _PAD - _PERSON_X
_CRUMB_WIDTH = NODE_W - _PAD - _PAD


def _fit(text: str, font: QFont, width: float) -> str:
    """Elide text with an ellipsis so it never exceeds the given pixel width."""
    return QFontMetricsF(font).elidedText(text, Qt.TextElideMode.ElideRight, width)


def node_font(bold: bool = False) -> QFont:
    font = QFont()
    font.setBold(bold)
    return font


def node_center(top_left: QPointF) -> QPointF:
    return QPointF(top_left.x() + NODE_W / _HALF, top_left.y() + NODE_H / _HALF)


def _blend(low: QColor, high: QColor, ratio: float) -> QColor:
    return QColor(
        int(low.red() + (high.red() - low.red()) * ratio),
        int(low.green() + (high.green() - low.green()) * ratio),
        int(low.blue() + (high.blue() - low.blue()) * ratio),
    )


def _sublabel(node) -> str:
    people = count_noun(node.headcount, "person", "people")
    if node.kind == KIND_DOMAIN:
        label = f"{node.category} · {count_noun(node.team_count, 'team')} · {people}"
        if node.contested_count:
            label = f"{label} · {node.contested_count} contested"
        return label
    if node.contested_count:
        return f"contested · {people}"
    decides = "decides locally" if node.authority_ratio >= _FULL else "escalates"
    return f"{decides} · {people}"


def _secondary(node) -> str:
    if not node.owner:
        return ""
    label = "lead" if node.kind == KIND_DOMAIN else "owner"
    return f"{label}: {node.owner}"


def _draw_person(scene: QGraphicsScene, rect: QRectF, color: QColor, node) -> None:
    pen = QPen(color, 2)
    empty = QBrush(Qt.BrushStyle.NoBrush)
    cx = rect.right() - _PERSON_X
    top = rect.y() + _PERSON_TOP
    scene.addEllipse(cx - _HEAD_R, top, _HEAD_R * _HALF, _HEAD_R * _HALF, pen, empty)
    scene.addLine(cx, top + _HEAD_R * _HALF, cx, top + _BODY_LEN, pen)
    scene.addLine(cx - _ARM, top + _ARM_Y, cx + _ARM, top + _ARM_Y, pen)
    scene.addLine(cx, top + _BODY_LEN, cx - _LEG, top + _BODY_LEN + _LEG_DROP, pen)
    scene.addLine(cx, top + _BODY_LEN, cx + _LEG, top + _BODY_LEN + _LEG_DROP, pen)
    if node.kind != KIND_DOMAIN and node.authority_ratio < _FULL:
        arrow = scene.addSimpleText(_ESCALATE, node_font(bold=True))
        arrow.setBrush(color)
        arrow.setPos(cx + _HEAD_R, top - _HEAD_R)


def draw_node(scene: QGraphicsScene, node, top_left: QPointF) -> QRectF:
    """Draw one node and its glyph and labels; return its rect for hit-testing."""
    rect = QRectF(top_left.x(), top_left.y(), NODE_W, NODE_H)
    path = QPainterPath()
    path.addRoundedRect(rect, CORNER, CORNER)
    fill = (
        map_palette().domain_fill
        if node.kind == KIND_DOMAIN
        else map_palette().team_fill
    )
    if node.contested_count:
        border = map_palette().contested
    else:
        border = _blend(
            map_palette().no_authority, map_palette().authority, node.authority_ratio
        )
    scene.addPath(path, QPen(border, 2), QBrush(fill))
    _draw_person(scene, rect, border, node)
    name_font = node_font(bold=True)
    name = scene.addSimpleText(_fit(node.label, name_font, _LABEL_WIDTH), name_font)
    name.setBrush(map_palette().text)
    name.setPos(rect.x() + _PAD, rect.y() + _PAD)
    sub_font = node_font()
    sub = scene.addSimpleText(_fit(_sublabel(node), sub_font, _LABEL_WIDTH), sub_font)
    sub.setBrush(map_palette().text_muted)
    sub.setPos(rect.x() + _PAD, rect.y() + _SUB_DROP + _PAD)
    secondary = _secondary(node)
    if secondary:
        line2 = scene.addSimpleText(_fit(secondary, sub_font, _LABEL_WIDTH), sub_font)
        line2.setBrush(map_palette().text_muted)
        line2.setPos(rect.x() + _PAD, rect.y() + _SUB_LINE2 + _PAD)
    return rect


def _node_rect(top_left: QPointF) -> QRectF:
    return QRectF(top_left.x(), top_left.y(), NODE_W, NODE_H)


def draw_edges(scene: QGraphicsScene, edges, positions: dict) -> None:
    """Draw each dependency edge as an arrow, with a weight label when above one.

    The run is border to border rather than centre to centre, so no line is
    painted across the inside of the box it leaves or the box it enters, and
    the head sits exactly where the line meets the target for every approach
    angle rather than only for the horizontal and vertical ones.
    """
    for edge in edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        span = edge_span(
            _node_rect(positions[edge.source]), _node_rect(positions[edge.target])
        )
        if span is None:
            continue
        start, end, angle = span
        scene.addLine(
            start.x(), start.y(), end.x(), end.y(), QPen(map_palette().edge, 1.5)
        )
        scene.addPolygon(
            arrow_head(end, angle, _ARROW),
            QPen(map_palette().edge),
            QBrush(map_palette().edge),
        )
        if edge.weight > 1:
            _draw_weight(scene, start, end, edge.weight)


def _draw_weight(scene: QGraphicsScene, start: QPointF, end: QPointF, weight) -> None:
    """Centre the count on the run rather than hanging it off the midpoint."""
    label = scene.addSimpleText(str(weight), node_font())
    label.setBrush(map_palette().text_muted)
    bounds = label.boundingRect()
    label.setPos(
        (start.x() + end.x()) / _HALF - bounds.width() / _HALF,
        (start.y() + end.y()) / _HALF - bounds.height(),
    )


def grid_positions(nodes, gap_x: float, gap_y: float) -> dict:
    """Lay a level's nodes on a near-square grid, left to right then down."""
    columns = max(1, math.ceil(math.sqrt(max(1, len(nodes)))))
    positions = {}
    for index, node in enumerate(nodes):
        row = index // columns
        column = index % columns
        positions[node.id] = QPointF(column * (NODE_W + gap_x), row * (NODE_H + gap_y))
    return positions


def draw_ring(scene_painter: QPainter, rect: QRectF) -> None:
    """One ring model everywhere: the green action ring outside a node."""
    outer = rect.adjusted(-RING_INSET, -RING_INSET, RING_INSET, RING_INSET)
    radius = CORNER + RING_INSET
    scene_painter.save()
    scene_painter.setPen(QPen(map_palette().ring, RING_PEN))
    scene_painter.setBrush(Qt.BrushStyle.NoBrush)
    scene_painter.drawRoundedRect(outer, radius, radius)
    scene_painter.restore()


def draw_breadcrumb(scene: QGraphicsScene, parent_name: str) -> QRectF:
    """Draw the back chip above the level; return its rect for hit-testing."""
    rect = QRectF(0, -(NODE_H + _GAP_Y), NODE_W, NODE_H / _HALF)
    scene.addRect(
        rect, QPen(map_palette().preview, 2), QBrush(map_palette().domain_fill)
    )
    crumb_font = node_font(bold=True)
    crumb = _fit(f"↑ Back · {parent_name}", crumb_font, _CRUMB_WIDTH)
    text = scene.addSimpleText(crumb, crumb_font)
    text.setBrush(map_palette().preview)
    text.setPos(rect.x() + _PAD, rect.y() + _PAD)
    return rect
