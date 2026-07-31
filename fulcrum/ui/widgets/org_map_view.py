"""A navigable map of an organisation, drawn on a graphics scene.

At the top level it shows the root domains (each a box aggregating its subtree)
plus any unassigned teams; clicking a domain or pressing Enter on the keyboard
cursor drills into it, and the back chip or Backspace climbs out. A node's border
runs from amber (no local authority) to teal (fully authoritative); inter-node
dependencies are drawn as arrows. Hovering a drillable domain or the back chip, or
moving the keyboard cursor onto a domain, rings it to show it can be opened; each
level is fit to the panel, with + and - stepping a per-level zoom over that fit.
Scene painting and the ring live in org_map_painter; this view owns
navigation, hit-testing and the overlay state.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from fulcrum.application.map_model import build_level
from fulcrum.domain.models import OrgState
from fulcrum.ui import ui_scale
from fulcrum.ui.map_palette import map_palette
from fulcrum.ui.widgets import org_map_painter as painter

# One ring model everywhere: green marks the node you can act on, whether
# reached by mouse (hover), keyboard (cursor) or affected by a change; muted
# so the large surround does not shout. The ring itself is painted by
# org_map_painter.draw_ring.

_MIN_HEIGHT = 340
_GAP_X = 64.0
_GAP_Y = 72.0
# User zoom multiplies the level's fitted scale: 1.0 is the fit itself (the
# floor the minus button returns to) and each step grows a quarter, capped
# so a level never blows past readable into absurd.
_FIT_ZOOM = 1.0
_USER_ZOOM_STEP = 1.25
_MAX_USER_ZOOM = 4.0
_MARGIN = 44.0
_FIT_MARGIN = painter.RING_INSET + painter.RING_PEN
_CLICK_SLOP = 4


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
        self.setBackgroundBrush(QBrush(map_palette().bg))
        self.setMinimumHeight(ui_scale.px(_MIN_HEIGHT))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._org: OrgState | None = None
        self._parent_id: str | None = None
        self._signature: object = None
        self._hot: list[tuple[QRectF, str, str]] = []
        self._up_rect: QRectF | None = None
        self._press_pos = None
        self._hover_id: str | None = None
        self._hover_back = False
        self._highlight: frozenset[str] = frozenset()
        self._cursor_id: str | None = None
        self._min_scale = 0.0
        self._user_zoom = _FIT_ZOOM
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    def apply_map_theme(self) -> None:
        """Repaint the canvas and scene in the current map palette."""
        self.setBackgroundBrush(QBrush(map_palette().bg))
        self._render()

    def set_org(self, org: OrgState) -> None:
        self._org = org
        if self._parent_id is not None and not any(
            d.id == self._parent_id for d in org.domains
        ):
            self._parent_id = None
        self._render()

    def set_highlight(self, node_ids) -> None:
        """Ring the given node ids to mark them as changed, then repaint."""
        self._highlight = frozenset(node_ids)
        self.viewport().update()

    def set_min_scale(self, scale: float) -> None:
        """Never fit smaller than this scale; scroll instead of shrinking tiny.

        The preview sets it so a many-node affected domain stays readable rather
        than being squeezed to fit, which the board level deliberately does.
        """
        self._min_scale = scale
        self._fit()

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
        positions = painter.grid_positions(nodes, _GAP_X, _GAP_Y)
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
            # Each level opens at its own fit; zoom is a per-level choice.
            self._user_zoom = _FIT_ZOOM
            self._fit()

    def _fit(self) -> None:
        bounds = self._scene.itemsBoundingRect()
        if bounds.isEmpty():
            return
        padded = bounds.adjusted(-_FIT_MARGIN, -_FIT_MARGIN, _FIT_MARGIN, _FIT_MARGIN)
        self.fitInView(padded, Qt.AspectRatioMode.KeepAspectRatio)
        if self._min_scale > 0.0 and self.transform().m11() < self._min_scale:
            # A many-node map would fit-to-shrink into something unreadable; hold
            # a readable floor and start at the top-left so the scrollbars open at
            # the far edges rather than centred.
            self.resetTransform()
            self.scale(self._min_scale, self._min_scale)
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().minimum())
            self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())
        if self._user_zoom != _FIT_ZOOM:
            self.scale(self._user_zoom, self._user_zoom)

    def zoom_in(self) -> None:
        """Step this level larger over its fitted scale."""
        self._apply_user_zoom(min(self._user_zoom * _USER_ZOOM_STEP, _MAX_USER_ZOOM))

    def zoom_out(self) -> None:
        """Step back toward the level's fitted scale, which is the floor."""
        self._apply_user_zoom(max(self._user_zoom / _USER_ZOOM_STEP, _FIT_ZOOM))

    def _apply_user_zoom(self, target: float) -> None:
        if target == self._user_zoom:
            return
        factor = target / self._user_zoom
        self._user_zoom = target
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.scale(factor, factor)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

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
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
        elif key == Qt.Key.Key_Minus:
            self.zoom_out()
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

    def drill_to(self, domain_id: str) -> None:
        """Enter directly at a domain's frame, as a complete-picture click.

        Mirrors _drill_at's click path so the board can hand this map a
        section chosen on the complete picture.
        """
        self._reset_hover()
        self._parent_id = domain_id
        self._cursor_id = domain_id
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

    def _cursor_rect(self) -> QRectF | None:
        if not self.hasFocus() or self._cursor_id is None:
            return None
        return self._rect_of(self._cursor_id)

    def drawForeground(self, scene_painter: QPainter, rect: QRectF) -> None:
        # Keyboard-selection ring first, then the hover ring over it, so
        # hovering the selected section still shows the open cue.
        for target in (self._cursor_rect(), self._hover_rect()):
            if target is not None:
                painter.draw_ring(scene_painter, target)
        for node_rect, _kind, node_id in self._hot:
            if node_id in self._highlight:
                painter.draw_ring(scene_painter, node_rect)
