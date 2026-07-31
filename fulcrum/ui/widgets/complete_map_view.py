"""A single complete picture of the whole organisation.

Domains are drawn as nested boxes holding their teams and sub-domains, with
every dependency drawn between the teams. It complements the drill-down map by
showing the entire structure at once rather than one level at a time; the
geometry comes from complete_map_layout, the scene painting lives in
complete_map_painter and this view owns navigation, hover and overlays.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from fulcrum.domain.models import OrgState
from fulcrum.ui.map_palette import map_palette
from fulcrum.ui.widgets import complete_map_painter as painter
from fulcrum.ui.widgets.complete_map_layout import (
    KIND_TEAM,
    ROOT_COLUMNS,
    SHELL_ID,
    SUMMARY_MAX_TEAMS,
    flow,
    root_boxes,
)

_MIN_SCALE = 0.15
_MAX_SCALE = 3.0
_ZOOM_STEP = 1.15
_FULL = 1.0
# Padding around the scene so edge nodes are not flush against the viewport edge
# when the full-size map is dragged to its limits.
_VIEW_MARGIN = 40.0
_CLICK_SLOP = 4
# The hover ring sits just outside the section border, the same open cue the
# drill map gives, in the same green as every other hover ring.
_RING_INSET = 5.0
_RING_PEN = 3.0


class CompleteMapView(QGraphicsView):
    """Draws the whole org at once: nested domain boxes, teams and all edges.

    As the board's default view it is also an entry point: clicking any
    domain emits domain_clicked so the board can drill straight into that
    section, and Enter or Down asks for the drill map (drill_requested),
    where the full keyboard cursor lives. Hovering a drillable section rings
    it to show a click opens it.
    """

    domain_clicked = Signal(str)
    drill_requested = Signal()

    def __init__(self, parent=None, drillable: bool = True) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setObjectName("CompleteMap")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(map_palette().bg))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # A display-only instance (the move record's before/after maps) has
        # no drill listener, so it never shows the open cue a click cannot
        # honour there.
        self._drillable = drillable
        self._org: OrgState | None = None
        self._summarize = False
        self._domain_rects: dict[str, QRectF] = {}
        self._press_pos = None
        self._hover_id: str | None = None
        self._anchor_on_show = False
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    def set_org(self, org: OrgState) -> None:
        self._org = org
        self._summarize = len(org.teams) > SUMMARY_MAX_TEAMS
        self._hover_id = None
        self._render()
        self.show_full_size()
        # The viewport may not have its real size yet (the board builds
        # before the window shows), which left the picture anchored mid
        # scene with the top and bottom entities cut off; re-anchor at the
        # next show so the topmost entity is where reading starts.
        self._anchor_on_show = True

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._anchor_on_show:
            self._anchor_on_show = False
            QTimer.singleShot(0, self.show_full_size)

    def apply_map_theme(self) -> None:
        """Repaint the canvas and scene in the current map palette."""
        self.setBackgroundBrush(QBrush(map_palette().bg))
        self._render()

    def mousePressEvent(self, event) -> None:
        self._press_pos = event.position()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if self._press_pos is None:
            return
        moved = (event.position() - self._press_pos).manhattanLength()
        self._press_pos = None
        if moved > _CLICK_SLOP:
            return
        clicked = self._domain_at(self.mapToScene(event.position().toPoint()))
        if clicked is not None:
            self._hover_id = None
            self.domain_clicked.emit(clicked)

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        if not self._drillable:
            return
        hovered = self._domain_at(self.mapToScene(event.position().toPoint()))
        if hovered != self._hover_id:
            self._hover_id = hovered
            self.viewport().update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        if self._hover_id is not None:
            self._hover_id = None
            self.viewport().update()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Down):
            self.drill_requested.emit()
            return
        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
            return
        if key == Qt.Key.Key_Minus:
            self.zoom_out()
            return
        super().keyPressEvent(event)

    def drawForeground(self, scene_painter: QPainter, rect: QRectF) -> None:
        if self._hover_id is None:
            return
        target = self._domain_rects.get(self._hover_id)
        if target is None:
            return
        outer = target.adjusted(-_RING_INSET, -_RING_INSET, _RING_INSET, _RING_INSET)
        radius = painter.CORNER + _RING_INSET
        scene_painter.save()
        scene_painter.setPen(QPen(map_palette().ring, _RING_PEN))
        scene_painter.setBrush(Qt.BrushStyle.NoBrush)
        scene_painter.drawRoundedRect(outer, radius, radius)
        scene_painter.restore()

    def _domain_at(self, scene_pos) -> str | None:
        """The deepest (smallest) domain under the point, or None."""
        best: str | None = None
        best_area = None
        for ident, rect in self._domain_rects.items():
            if rect.contains(scene_pos):
                area = rect.width() * rect.height()
                if best_area is None or area < best_area:
                    best, best_area = ident, area
        return best

    def show_full_size(self) -> None:
        """Show the whole picture at natural size, scrolled to the top-left.

        The complete map is read at full scale and dragged around with the hand
        cursor rather than shrunk to fit, so the tree stays legible however large
        it grows; panning and the wheel reach the rest.
        """
        self.resetTransform()
        bounds = self._scene.itemsBoundingRect()
        if not bounds.isEmpty():
            self.setSceneRect(
                bounds.adjusted(
                    -_VIEW_MARGIN, -_VIEW_MARGIN, _VIEW_MARGIN, _VIEW_MARGIN
                )
            )
        hbar = self.horizontalScrollBar()
        vbar = self.verticalScrollBar()
        hbar.setValue(hbar.minimum())
        vbar.setValue(vbar.minimum())

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = _ZOOM_STEP if delta > 0 else _FULL / _ZOOM_STEP
        self._zoom(factor, QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def zoom_in(self) -> None:
        """Step the picture larger, anchored on the viewport centre."""
        self._zoom(_ZOOM_STEP, QGraphicsView.ViewportAnchor.AnchorViewCenter)

    def zoom_out(self) -> None:
        """Step the picture smaller, anchored on the viewport centre."""
        self._zoom(_FULL / _ZOOM_STEP, QGraphicsView.ViewportAnchor.AnchorViewCenter)

    def _zoom(self, factor: float, anchor) -> None:
        target = self.transform().m11() * factor
        if _MIN_SCALE <= target <= _MAX_SCALE:
            self.setTransformationAnchor(anchor)
            self.scale(factor, factor)

    def _render(self) -> None:
        self._scene.clear()
        if self._org is None:
            return
        placed, _, _ = flow(root_boxes(self._org, self._summarize), ROOT_COLUMNS)
        rects: dict[str, QRectF] = {}
        domains: list = []
        teams: list = []
        for rx, ry, box in placed:
            self._collect(box, rx, ry, rects, domains, teams)
        # The domain rectangles double as the click targets for drilling;
        # the synthetic Shell is not a modelled unit, so it is not one.
        self._domain_rects = {
            box.ident: QRectF(x, y, box.w, box.h)
            for x, y, box in domains
            if box.ident != SHELL_ID
        }
        for x, y, box in domains:
            painter.draw_domain(self._scene, self._org, self._summarize, x, y, box)
        for x, y, box in teams:
            painter.draw_team(self._scene, self._org, x, y, box)
        painter.draw_edges(self._scene, self._org, rects)

    def _collect(self, box, x, y, rects, domains, teams) -> None:
        # Domains register a rectangle too, so an authored unit-level
        # dependency draws between the unit rectangles themselves.
        rects[box.ident] = QRectF(x, y, box.w, box.h)
        if box.kind == KIND_TEAM:
            teams.append((x, y, box))
            return
        domains.append((x, y, box))
        for rx, ry, child in box.children:
            self._collect(child, x + rx, y + ry, rects, domains, teams)
