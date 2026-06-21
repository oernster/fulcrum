"""A navigable map of an organisation, drawn on a graphics scene.

At the top level it shows the root domains (each a box aggregating its subtree)
plus any unassigned teams; clicking a domain or pressing Enter on the keyboard
cursor drills into it, and the back chip or Backspace climbs out. A node's border
runs from amber (no local authority) to teal (fully authoritative); inter-node
dependencies are drawn as arrows. Hovering a drillable domain or the back chip, or
moving the keyboard cursor onto a domain, rings it to show it can be opened; each
level is fit to the panel and navigation is by drilling in rather than zooming.
Scene painting lives in org_map_painter; this view owns navigation and overlays.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from fulcrum.application.map_model import build_level
from fulcrum.domain.models import OrgState
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets import org_map_painter as painter

_HOVER_RING = QColor("#60a5fa")
_CHANGE_RING = QColor("#22d3ee")
_CURSOR_RING = QColor("#f59e0b")
_BG = QColor("#0d0f12")

_MIN_HEIGHT = 340
_GAP_X = 64.0
_GAP_Y = 72.0
_MARGIN = 44.0
_DRILL_INSET = 5.0
_DRILL_PEN = 3.0
_FIT_MARGIN = _DRILL_INSET + _DRILL_PEN
_CLICK_SLOP = 4
_PREVIEW_INSET = 2
_PREVIEW_TEXT_X = 8
_PREVIEW_TEXT_Y = 6
_PREVIEW_TEXT_DROP = 24


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
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
        self._cursor_id: str | None = None
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
        painter.draw_edges(self._scene, edges, positions)
        for node in nodes:
            rect = painter.draw_node(self._scene, node, positions[node.id])
            self._hot.append((rect, node.kind, node.id))
        if self._parent_id is not None:
            self._up_rect = painter.draw_breadcrumb(
                self._scene, self._domain_name(self._parent_id)
            )
        self._sync_cursor()
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
                column * (painter.NODE_W + _GAP_X), row * (painter.NODE_H + _GAP_Y)
            )
        return positions

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

    def _domain_ids(self) -> list[str]:
        return [nid for _rect, kind, nid in self._hot if kind == painter.KIND_DOMAIN]

    def _sync_cursor(self) -> None:
        ids = self._domain_ids()
        if self._cursor_id not in ids:
            self._cursor_id = ids[0] if ids else None

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

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._drill_cursor()
        elif key in (Qt.Key.Key_Backspace, Qt.Key.Key_Escape):
            self._climb()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self._step_cursor(1)
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self._step_cursor(-1)
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._sync_cursor()
        self.viewport().update()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.viewport().update()

    def _step_cursor(self, delta: int) -> None:
        ids = self._domain_ids()
        if not ids:
            return
        if self._cursor_id in ids:
            index = (ids.index(self._cursor_id) + delta) % len(ids)
        else:
            index = 0
        self._cursor_id = ids[index]
        self.viewport().update()

    def _drill_cursor(self) -> None:
        if self._cursor_id is not None:
            self._reset_hover()
            self._parent_id = self._cursor_id
            self._render()
            self.drilled.emit(self._parent_id)

    def _climb(self) -> None:
        if self._parent_id is not None:
            self._reset_hover()
            self._parent_id = self._domain_parent(self._parent_id)
            self._render()
            self.drilled.emit(self._parent_id)

    def _drill_at(self, scene_pos: QPointF) -> None:
        if self._up_rect is not None and self._up_rect.contains(scene_pos):
            self._climb()
            return
        node_id = self._domain_at(scene_pos)
        if node_id is not None:
            self._reset_hover()
            self._parent_id = node_id
            self._cursor_id = node_id
            self._render()
            self.drilled.emit(self._parent_id)

    def _domain_at(self, scene_pos: QPointF) -> str | None:
        for rect, kind, node_id in self._hot:
            if kind == painter.KIND_DOMAIN and rect.contains(scene_pos):
                return node_id
        return None

    def _reset_hover(self) -> None:
        self._hover_id = None
        self._hover_back = False

    def _hover_rect(self) -> QRectF | None:
        if self._hover_back and self._up_rect is not None:
            return self._up_rect
        if self._hover_id is not None:
            return self._rect_of(self._hover_id)
        return None

    def _rect_of(self, node_id: str) -> QRectF | None:
        for rect, _kind, candidate in self._hot:
            if candidate == node_id:
                return rect
        return None

    def drawForeground(self, scene_painter: QPainter, rect: QRectF) -> None:
        self._paint_hover_ring(scene_painter)
        self._paint_cursor_ring(scene_painter)
        for node_rect, _kind, node_id in self._hot:
            if node_id in self._highlight:
                self._draw_ring(scene_painter, node_rect, _CHANGE_RING)
        if not self._preview:
            return
        scene_painter.save()
        scene_painter.resetTransform()
        frame = (
            self.viewport()
            .rect()
            .adjusted(_PREVIEW_INSET, _PREVIEW_INSET, -_PREVIEW_INSET, -_PREVIEW_INSET)
        )
        scene_painter.setPen(QPen(painter.PREVIEW, 2))
        scene_painter.setBrush(Qt.BrushStyle.NoBrush)
        scene_painter.drawRect(frame)
        scene_painter.drawText(
            frame.adjusted(_PREVIEW_TEXT_X, _PREVIEW_TEXT_Y, 0, 0).topLeft()
            + QPointF(0, _PREVIEW_TEXT_DROP).toPoint(),
            "Preview",
        )
        scene_painter.restore()

    def _paint_hover_ring(self, scene_painter: QPainter) -> None:
        target = self._hover_rect()
        if target is not None:
            self._draw_ring(scene_painter, target, _HOVER_RING)

    def _paint_cursor_ring(self, scene_painter: QPainter) -> None:
        if not self.hasFocus() or self._cursor_id is None:
            return
        target = self._rect_of(self._cursor_id)
        if target is not None:
            self._draw_ring(scene_painter, target, _CURSOR_RING)

    def _draw_ring(self, scene_painter: QPainter, rect: QRectF, color: QColor) -> None:
        outer = rect.adjusted(-_DRILL_INSET, -_DRILL_INSET, _DRILL_INSET, _DRILL_INSET)
        radius = painter.CORNER + _DRILL_INSET
        scene_painter.save()
        scene_painter.setPen(QPen(color, _DRILL_PEN))
        scene_painter.setBrush(Qt.BrushStyle.NoBrush)
        scene_painter.drawRoundedRect(outer, radius, radius)
        scene_painter.restore()
