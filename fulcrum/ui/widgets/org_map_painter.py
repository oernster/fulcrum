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
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QGraphicsScene

KIND_DOMAIN = "domain"
NODE_W = 240.0
NODE_H = 88.0
CORNER = 10.0
PREVIEW = QColor("#fbbf24")

_AUTHORITY = QColor("#34d399")
_NO_AUTHORITY = QColor("#f59e0b")
_TEAM_FILL = QColor("#1a1e24")
_DOMAIN_FILL = QColor("#222831")
_TEXT = QColor("#e6e9ee")
_TEXT_MUTED = QColor("#9aa3af")
_EDGE = QColor("#5b6470")

_GAP_Y = 72.0
_PAD = 12.0
_SUB_DROP = 24.0
_SUB_LINE2 = 42.0
_ARROW = 11.0
_HALF = 2.0
_FULL = 1.0
_ARROW_SPREAD = math.pi / 6
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
    people = f"{node.headcount:,} people"
    if node.kind == KIND_DOMAIN:
        return f"{node.category} · {node.team_count} teams · {people}"
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
    fill = _DOMAIN_FILL if node.kind == KIND_DOMAIN else _TEAM_FILL
    border = _blend(_NO_AUTHORITY, _AUTHORITY, node.authority_ratio)
    scene.addPath(path, QPen(border, 2), QBrush(fill))
    _draw_person(scene, rect, border, node)
    name_font = node_font(bold=True)
    name = scene.addSimpleText(_fit(node.label, name_font, _LABEL_WIDTH), name_font)
    name.setBrush(_TEXT)
    name.setPos(rect.x() + _PAD, rect.y() + _PAD)
    sub_font = node_font()
    sub = scene.addSimpleText(_fit(_sublabel(node), sub_font, _LABEL_WIDTH), sub_font)
    sub.setBrush(_TEXT_MUTED)
    sub.setPos(rect.x() + _PAD, rect.y() + _SUB_DROP + _PAD)
    secondary = _secondary(node)
    if secondary:
        line2 = scene.addSimpleText(_fit(secondary, sub_font, _LABEL_WIDTH), sub_font)
        line2.setBrush(_TEXT_MUTED)
        line2.setPos(rect.x() + _PAD, rect.y() + _SUB_LINE2 + _PAD)
    return rect


def _draw_arrow(scene: QGraphicsScene, start: QPointF, end: QPointF) -> None:
    angle = math.atan2(end.y() - start.y(), end.x() - start.x())
    tip = QPointF(
        end.x() - NODE_W / _HALF * math.cos(angle),
        end.y() - NODE_H / _HALF * math.sin(angle),
    )
    left = QPointF(
        tip.x() - _ARROW * math.cos(angle - _ARROW_SPREAD),
        tip.y() - _ARROW * math.sin(angle - _ARROW_SPREAD),
    )
    right = QPointF(
        tip.x() - _ARROW * math.cos(angle + _ARROW_SPREAD),
        tip.y() - _ARROW * math.sin(angle + _ARROW_SPREAD),
    )
    scene.addPolygon(QPolygonF([tip, left, right]), QPen(_EDGE), QBrush(_EDGE))


def draw_edges(scene: QGraphicsScene, edges, positions: dict) -> None:
    """Draw each dependency edge as an arrow, with a weight label when above one."""
    for edge in edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        start = node_center(positions[edge.source])
        end = node_center(positions[edge.target])
        scene.addLine(start.x(), start.y(), end.x(), end.y(), QPen(_EDGE, 1.5))
        _draw_arrow(scene, start, end)
        if edge.weight > 1:
            label = scene.addSimpleText(str(edge.weight), node_font())
            label.setBrush(_TEXT_MUTED)
            label.setPos((start.x() + end.x()) / _HALF, (start.y() + end.y()) / _HALF)


def draw_breadcrumb(scene: QGraphicsScene, parent_name: str) -> QRectF:
    """Draw the back chip above the level; return its rect for hit-testing."""
    rect = QRectF(0, -(NODE_H + _GAP_Y), NODE_W, NODE_H / _HALF)
    scene.addRect(rect, QPen(PREVIEW, 2), QBrush(_DOMAIN_FILL))
    crumb_font = node_font(bold=True)
    crumb = _fit(f"↑ Back · {parent_name}", crumb_font, _CRUMB_WIDTH)
    text = scene.addSimpleText(crumb, crumb_font)
    text.setBrush(PREVIEW)
    text.setPos(rect.x() + _PAD, rect.y() + _PAD)
    return rect
