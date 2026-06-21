"""A navigable map of an organisation, drawn on a graphics scene.

At the top level it shows the root domains (each a box aggregating its subtree)
plus any unassigned teams; clicking a domain drills into it and the back chip
climbs out. A node's border runs from amber (no local authority) to teal (fully
authoritative); inter-node dependencies are drawn as arrows. Hovering a
drillable domain or the back chip rings it in blue to show you can click it;
each level is fit to the panel and navigation is by drilling in rather than
zooming. The set_org / set_preview contract matches the board's expectations.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from fulcrum.application.map_model import build_level
from fulcrum.domain.models import OrgState
from fulcrum.ui import ui_scale

_KIND_DOMAIN = "domain"
_AUTHORITY = QColor("#34d399")
_NO_AUTHORITY = QColor("#f59e0b")
_TEAM_FILL = QColor("#1a1e24")
_DOMAIN_FILL = QColor("#222831")
_TEXT = QColor("#e6e9ee")
_TEXT_MUTED = QColor("#9aa3af")
_EDGE = QColor("#5b6470")
_PREVIEW = QColor("#fbbf24")
_HOVER_RING = QColor("#60a5fa")
_CHANGE_RING = QColor("#22d3ee")
_BG = QColor("#0d0f12")

_MIN_HEIGHT = 340
_NODE_W = 240.0
_NODE_H = 88.0
_GAP_X = 64.0
_GAP_Y = 72.0
_MARGIN = 44.0
_PAD = 12.0
_SUB_DROP = 24.0
_SUB_LINE2 = 42.0
_CORNER = 10.0
_DRILL_INSET = 5.0
_DRILL_PEN = 3.0
_FIT_MARGIN = _DRILL_INSET + _DRILL_PEN
_ARROW = 11.0
_CLICK_SLOP = 4
_FULL = 1.0
_HALF = 2.0
_PREVIEW_INSET = 2
_PREVIEW_TEXT_X = 8
_PREVIEW_TEXT_Y = 6
_PERSON_X = 26.0
_PERSON_TOP = 14.0
_HEAD_R = 5.0
_BODY_LEN = 20.0
_ARM_Y = 13.0
_ARM = 8.0
_LEG = 6.0
_LEG_DROP = 9.0
_ESCALATE = "↑"


def _blend(low: QColor, high: QColor, ratio: float) -> QColor:
    return QColor(
        int(low.red() + (high.red() - low.red()) * ratio),
        int(low.green() + (high.green() - low.green()) * ratio),
        int(low.blue() + (high.blue() - low.blue()) * ratio),
    )


def _font(bold: bool = False) -> QFont:
    font = QFont()
    font.setBold(bold)
    return font


def _center(top_left: QPointF) -> QPointF:
    return QPointF(top_left.x() + _NODE_W / _HALF, top_left.y() + _NODE_H / _HALF)


class OrgMapView(QGraphicsView):
    """Paints the OrgState as a navigable, drill-down domain-and-team map."""

    # Emitted when the user drills into a domain or climbs back out, carrying the
    # domain now in focus (a domain id) or None at the top level. The board uses
    # it to focus play on the drilled section.
    drilled = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(_BG))
        self.setMinimumHeight(ui_scale.px(_MIN_HEIGHT))
        self._org: OrgState | None = None
        self._preview = False
        self._parent_id: str | None = None
        self._signature: object = None
        self._hot: list[tuple[QRectF, str, str]] = []
        self._up_rect: QRectF | None = None
        self._press_pos = None
        self._hover_id: str | None = None
        self._hover_back = False
        self._highlight: frozenset[str] = frozenset()
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    def set_org(self, org: OrgState) -> None:
        self._org = org
        if self._parent_id is not None and not any(
            d.id == self._parent_id for d in org.domains
        ):
            self._parent_id = None
        self._render()

    def set_preview(self, value: bool) -> None:
        self._preview = value
        self.viewport().update()

    def set_highlight(self, node_ids) -> None:
        """Ring the given node ids to mark them as changed, then repaint."""
        self._highlight = frozenset(node_ids)
        self.viewport().update()

    def reset_view(self) -> None:
        """Return to the top level, for when a fresh org is loaded."""
        self._parent_id = None
        self._reset_hover()

    def fit_to_contents(self) -> None:
        """Fit the whole scene into the viewport, after a resize or a show."""
        self._fit()

    def _render(self) -> None:
        self._scene.clear()
        self._hot = []
        self._up_rect = None
        if self._org is None:
            return
        nodes, edges = build_level(self._org, self._parent_id)
        positions = self._positions(nodes)
        self._draw_edges(edges, positions)
        for node in nodes:
            self._draw_node(node, positions[node.id])
        self._draw_breadcrumb()
        bounds = self._scene.itemsBoundingRect().adjusted(
            -_MARGIN, -_MARGIN, _MARGIN, _MARGIN
        )
        self._scene.setSceneRect(bounds)
        signature = (self._parent_id, len(nodes))
        if signature != self._signature:
            self._signature = signature
            self._fit()

    def _fit(self) -> None:
        bounds = self._scene.itemsBoundingRect()
        if not bounds.isEmpty():
            padded = bounds.adjusted(
                -_FIT_MARGIN, -_FIT_MARGIN, _FIT_MARGIN, _FIT_MARGIN
            )
            self.fitInView(padded, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def _positions(self, nodes) -> dict:
        columns = max(1, math.ceil(math.sqrt(max(1, len(nodes)))))
        positions = {}
        for index, node in enumerate(nodes):
            row = index // columns
            column = index % columns
            positions[node.id] = QPointF(
                column * (_NODE_W + _GAP_X), row * (_NODE_H + _GAP_Y)
            )
        return positions

    def _draw_node(self, node, top_left: QPointF) -> None:
        rect = QRectF(top_left.x(), top_left.y(), _NODE_W, _NODE_H)
        path = QPainterPath()
        path.addRoundedRect(rect, _CORNER, _CORNER)
        fill = _DOMAIN_FILL if node.kind == _KIND_DOMAIN else _TEAM_FILL
        border = _blend(_NO_AUTHORITY, _AUTHORITY, node.authority_ratio)
        self._scene.addPath(path, QPen(border, 2), QBrush(fill))
        self._draw_person(rect, border, node)
        name = self._scene.addSimpleText(node.label, _font(bold=True))
        name.setBrush(_TEXT)
        name.setPos(rect.x() + _PAD, rect.y() + _PAD)
        sub = self._scene.addSimpleText(self._sublabel(node), _font())
        sub.setBrush(_TEXT_MUTED)
        sub.setPos(rect.x() + _PAD, rect.y() + _SUB_DROP + _PAD)
        secondary = self._secondary(node)
        if secondary:
            line2 = self._scene.addSimpleText(secondary, _font())
            line2.setBrush(_TEXT_MUTED)
            line2.setPos(rect.x() + _PAD, rect.y() + _SUB_LINE2 + _PAD)
        self._hot.append((rect, node.kind, node.id))

    def _draw_person(self, rect: QRectF, color: QColor, node) -> None:
        pen = QPen(color, 2)
        empty = QBrush(Qt.BrushStyle.NoBrush)
        cx = rect.right() - _PERSON_X
        top = rect.y() + _PERSON_TOP
        self._scene.addEllipse(
            cx - _HEAD_R, top, _HEAD_R * _HALF, _HEAD_R * _HALF, pen, empty
        )
        self._scene.addLine(cx, top + _HEAD_R * _HALF, cx, top + _BODY_LEN, pen)
        self._scene.addLine(cx - _ARM, top + _ARM_Y, cx + _ARM, top + _ARM_Y, pen)
        self._scene.addLine(
            cx, top + _BODY_LEN, cx - _LEG, top + _BODY_LEN + _LEG_DROP, pen
        )
        self._scene.addLine(
            cx, top + _BODY_LEN, cx + _LEG, top + _BODY_LEN + _LEG_DROP, pen
        )
        if node.kind != _KIND_DOMAIN and node.authority_ratio < _FULL:
            arrow = self._scene.addSimpleText(_ESCALATE, _font(bold=True))
            arrow.setBrush(color)
            arrow.setPos(cx + _HEAD_R, top - _HEAD_R)

    @staticmethod
    def _sublabel(node) -> str:
        people = f"{node.headcount:,} people"
        if node.kind == _KIND_DOMAIN:
            return f"{node.category} · {node.team_count} teams · {people}"
        decides = "decides locally" if node.authority_ratio >= _FULL else "escalates"
        return f"{decides} · {people}"

    @staticmethod
    def _secondary(node) -> str:
        if not node.owner:
            return ""
        label = "lead" if node.kind == _KIND_DOMAIN else "owner"
        return f"{label}: {node.owner}"

    def _draw_edges(self, edges, positions: dict) -> None:
        for edge in edges:
            if edge.source not in positions or edge.target not in positions:
                continue
            start = _center(positions[edge.source])
            end = _center(positions[edge.target])
            self._scene.addLine(
                start.x(), start.y(), end.x(), end.y(), QPen(_EDGE, 1.5)
            )
            self._draw_arrow(start, end)
            if edge.weight > 1:
                label = self._scene.addSimpleText(str(edge.weight), _font())
                label.setBrush(_TEXT_MUTED)
                label.setPos(
                    (start.x() + end.x()) / _HALF, (start.y() + end.y()) / _HALF
                )

    def _draw_arrow(self, start: QPointF, end: QPointF) -> None:
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        tip = QPointF(
            end.x() - _NODE_W / _HALF * math.cos(angle),
            end.y() - _NODE_H / _HALF * math.sin(angle),
        )
        left = QPointF(
            tip.x() - _ARROW * math.cos(angle - math.pi / 6),
            tip.y() - _ARROW * math.sin(angle - math.pi / 6),
        )
        right = QPointF(
            tip.x() - _ARROW * math.cos(angle + math.pi / 6),
            tip.y() - _ARROW * math.sin(angle + math.pi / 6),
        )
        self._scene.addPolygon(
            QPolygonF([tip, left, right]), QPen(_EDGE), QBrush(_EDGE)
        )

    def _draw_breadcrumb(self) -> None:
        if self._parent_id is None:
            return
        rect = QRectF(0, -(_NODE_H + _GAP_Y), _NODE_W, _NODE_H / _HALF)
        self._scene.addRect(rect, QPen(_PREVIEW, 2), QBrush(_DOMAIN_FILL))
        text = self._scene.addSimpleText(
            f"↑ Back · {self._domain_name(self._parent_id)}", _font(bold=True)
        )
        text.setBrush(_PREVIEW)
        text.setPos(rect.x() + _PAD, rect.y() + _PAD)
        self._up_rect = rect

    def _domain_name(self, domain_id: str) -> str:
        for domain in self._org.domains:
            if domain.id == domain_id:
                return domain.name
        return domain_id

    def _domain_parent(self, domain_id: str) -> str | None:
        for domain in self._org.domains:
            if domain.id == domain_id:
                return domain.parent_id
        return None

    def mousePressEvent(self, event) -> None:
        self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if self._press_pos is None:
            return
        moved = (event.position().toPoint() - self._press_pos).manhattanLength()
        self._press_pos = None
        if moved <= _CLICK_SLOP:
            self._drill_at(self.mapToScene(event.position().toPoint()))

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        pos = self.mapToScene(event.position().toPoint())
        domain = self._domain_at(pos)
        back = self._up_rect is not None and self._up_rect.contains(pos)
        if domain != self._hover_id or back != self._hover_back:
            self._hover_id = domain
            self._hover_back = back
            self.viewport().update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        if self._hover_id is not None or self._hover_back:
            self._reset_hover()
            self.viewport().update()

    def _drill_at(self, scene_pos: QPointF) -> None:
        if self._up_rect is not None and self._up_rect.contains(scene_pos):
            self._reset_hover()
            self._parent_id = self._domain_parent(self._parent_id)
            self._render()
            self.drilled.emit(self._parent_id)
            return
        node_id = self._domain_at(scene_pos)
        if node_id is not None:
            self._reset_hover()
            self._parent_id = node_id
            self._render()
            self.drilled.emit(self._parent_id)

    def _domain_at(self, scene_pos: QPointF) -> str | None:
        for rect, kind, node_id in self._hot:
            if kind == _KIND_DOMAIN and rect.contains(scene_pos):
                return node_id
        return None

    def _reset_hover(self) -> None:
        self._hover_id = None
        self._hover_back = False

    def _hover_rect(self) -> QRectF | None:
        if self._hover_back and self._up_rect is not None:
            return self._up_rect
        if self._hover_id is not None:
            for rect, _kind, node_id in self._hot:
                if node_id == self._hover_id:
                    return rect
        return None

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        self._paint_hover_ring(painter)
        for node_rect, _kind, node_id in self._hot:
            if node_id in self._highlight:
                self._draw_ring(painter, node_rect, _CHANGE_RING)
        if not self._preview:
            return
        painter.save()
        painter.resetTransform()
        frame = (
            self.viewport()
            .rect()
            .adjusted(_PREVIEW_INSET, _PREVIEW_INSET, -_PREVIEW_INSET, -_PREVIEW_INSET)
        )
        painter.setPen(QPen(_PREVIEW, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(frame)
        painter.drawText(
            frame.adjusted(_PREVIEW_TEXT_X, _PREVIEW_TEXT_Y, 0, 0).topLeft()
            + QPointF(0, _SUB_DROP).toPoint(),
            "Preview",
        )
        painter.restore()

    def _paint_hover_ring(self, painter: QPainter) -> None:
        target = self._hover_rect()
        if target is not None:
            self._draw_ring(painter, target, _HOVER_RING)

    def _draw_ring(self, painter: QPainter, rect: QRectF, color: QColor) -> None:
        outer = rect.adjusted(-_DRILL_INSET, -_DRILL_INSET, _DRILL_INSET, _DRILL_INSET)
        painter.save()
        painter.setPen(QPen(color, _DRILL_PEN))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(outer, _CORNER + _DRILL_INSET, _CORNER + _DRILL_INSET)
        painter.restore()
