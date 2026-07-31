"""A single complete picture of the whole organisation.

Domains are drawn as nested boxes holding their teams and sub-domains, with
every dependency drawn between the teams. It complements the drill-down map by
showing the entire structure at once rather than one level at a time; the
geometry comes from complete_map_layout and this module draws and interacts.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from fulcrum.domain.hierarchy import headcount_in_domain, teams_in_domain
from fulcrum.domain.models import Domain, OrgState
from fulcrum.domain.simulation import is_contested
from fulcrum.shared.text import count_noun
from fulcrum.ui.map_palette import map_palette
from fulcrum.ui.widgets.complete_map_edges import direct_is_clear, route_edges
from fulcrum.ui.widgets.complete_map_layout import (
    HALF,
    KIND_TEAM,
    PAD,
    ROOT_COLUMNS,
    SHELL_DETAIL,
    SHELL_ID,
    SHELL_LABEL,
    SUMMARY_MAX_TEAMS,
    TEAM_H,
    flow,
    is_summary,
    root_boxes,
)

_CORNER = 10.0
_PEN_W = 2
_ARROW = 9.0
_NAME_DY = 8.0
_SUB_DY = 31.0
_DOMAIN_CATEGORY_DY = 6.0
_DOMAIN_NAME_DY = 21.0
_DOMAIN_LEAD_DY = 38.0
_MIN_SCALE = 0.15
_MAX_SCALE = 3.0
_ZOOM_STEP = 1.15
_FULL = 1.0
# Padding around the scene so edge nodes are not flush against the viewport edge
# when the full-size map is dragged to its limits.
_VIEW_MARGIN = 40.0
_EDGE_PEN_W = 1.5
# A hub's counted trunk draws slightly heavier than a single edge, so the
# merge reads as "many wires" at a glance.
_TRUNK_PEN_W = 2.5
_CLICK_SLOP = 4
_SHELL_DASH = (4, 3)


def _font(bold: bool = False) -> QFont:
    font = QFont()
    font.setBold(bold)
    return font


def _blend(low: QColor, high: QColor, ratio: float) -> QColor:
    return QColor(
        int(low.red() + (high.red() - low.red()) * ratio),
        int(low.green() + (high.green() - low.green()) * ratio),
        int(low.blue() + (high.blue() - low.blue()) * ratio),
    )


class CompleteMapView(QGraphicsView):
    """Draws the whole org at once: nested domain boxes, teams and all edges.

    As the board's default view it is also an entry point: clicking any
    domain emits domain_clicked so the board can drill straight into that
    section, and Enter or Down asks for the drill map (drill_requested),
    where the full keyboard cursor lives.
    """

    domain_clicked = Signal(str)
    drill_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setObjectName("CompleteMap")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(map_palette().bg))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._org: OrgState | None = None
        self._summarize = False
        self._domain_rects: dict[str, QRectF] = {}
        self._press_pos = None
        self._anchor_on_show = False

    def set_org(self, org: OrgState) -> None:
        self._org = org
        self._summarize = len(org.teams) > SUMMARY_MAX_TEAMS
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
            self.domain_clicked.emit(clicked)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Down):
            self.drill_requested.emit()
            return
        super().keyPressEvent(event)

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
        target = self.transform().m11() * factor
        if _MIN_SCALE <= target <= _MAX_SCALE:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
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
            self._draw_domain(x, y, box)
        for x, y, box in teams:
            self._draw_team(x, y, box)
        self._draw_edges(rects)

    def _draw_edges(self, rects: dict[str, QRectF]) -> None:
        """Straight lines where nothing is in the way; routed lanes otherwise.

        The router fans each box's connections, hops crossings and merges a
        hub's edges into one counted trunk per direction, so no dependency
        is ever drawn through a box it has nothing to do with and no box
        drowns in lines.
        """
        if not rects:
            return
        diagram_right = max(rect.right() for rect in rects.values())
        routed: list[tuple[str, str]] = []
        for dep in self._org.dependencies:
            if dep.upstream not in rects or dep.downstream not in rects:
                continue
            source, target = rects[dep.upstream], rects[dep.downstream]
            if direct_is_clear(source, target, rects):
                self._draw_edge(source.center(), target.center())
                continue
            routed.append((dep.upstream, dep.downstream))
        drawing = route_edges(tuple(routed), rects, diagram_right)
        for path, is_trunk in drawing.paths:
            width = _TRUNK_PEN_W if is_trunk else _EDGE_PEN_W
            self._scene.addPath(path, QPen(map_palette().edge, width))
        for arrow in drawing.arrows:
            self._scene.addPolygon(
                arrow, QPen(map_palette().edge), QBrush(map_palette().edge)
            )
        for text, position in drawing.labels:
            label = self._scene.addSimpleText(text, _font(bold=True))
            label.setBrush(map_palette().text_muted)
            label.setPos(position)

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

    def _domain(self, ident: str) -> Domain:
        return next(domain for domain in self._org.domains if domain.id == ident)

    def _draw_domain(self, x, y, box) -> None:
        if box.ident == SHELL_ID:
            self._draw_shell(x, y, box)
            return
        domain = self._domain(box.ident)
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, box.w, box.h), _CORNER, _CORNER)
        self._scene.addPath(
            path,
            QPen(map_palette().no_authority, _PEN_W),
            QBrush(map_palette().domain_fill),
        )
        people = headcount_in_domain(self._org, domain.id)
        detail = f"{domain.category} · {count_noun(people, 'person', 'people')}"
        if is_summary(domain, self._summarize):
            teams = len(teams_in_domain(self._org, domain.id))
            detail = f"{detail} · {count_noun(teams, 'team')}"
        category = self._scene.addSimpleText(detail, _font())
        category.setBrush(map_palette().no_authority)
        category.setPos(x + PAD, y + _DOMAIN_CATEGORY_DY)
        name = self._scene.addSimpleText(domain.name, _font(bold=True))
        name.setBrush(map_palette().text)
        name.setPos(x + PAD, y + _DOMAIN_NAME_DY)
        if domain.lead:
            lead = self._scene.addSimpleText(f"lead: {domain.lead}", _font())
            lead.setBrush(map_palette().text_muted)
            lead.setPos(x + PAD, y + _DOMAIN_LEAD_DY)

    def _draw_shell(self, x, y, box) -> None:
        """The synthetic Shell: dashed and muted, visibly not modelled."""
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, box.w, box.h), _CORNER, _CORNER)
        pen = QPen(map_palette().text_muted, _PEN_W)
        pen.setDashPattern(_SHELL_DASH)
        self._scene.addPath(path, pen, QBrush(Qt.BrushStyle.NoBrush))
        name = self._scene.addSimpleText(SHELL_LABEL, _font(bold=True))
        name.setBrush(map_palette().text_muted)
        name.setPos(x + PAD, y + _DOMAIN_NAME_DY)
        detail = self._scene.addSimpleText(SHELL_DETAIL, _font())
        detail.setBrush(map_palette().text_muted)
        detail.setPos(x + PAD, y + _DOMAIN_CATEGORY_DY)

    def _draw_team(self, x, y, box) -> None:
        team = self._org.team(box.ident)
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, box.w, box.h), _CORNER, _CORNER)
        contested = is_contested(self._org, team)
        if contested:
            border = map_palette().contested
        else:
            ratio = _FULL if team.has_local_authority else 0.0
            border = _blend(map_palette().no_authority, map_palette().authority, ratio)
        self._scene.addPath(path, QPen(border, _PEN_W), QBrush(map_palette().team_fill))
        name = self._scene.addSimpleText(team.name, _font(bold=True))
        name.setBrush(map_palette().text)
        name.setPos(x + PAD, y + _NAME_DY)
        if contested:
            status = "contested"
        elif team.has_local_authority:
            status = "decides locally"
        else:
            status = "escalates"
        sub_text = f"{status} · {count_noun(team.headcount, 'person', 'people')}"
        sub = self._scene.addSimpleText(sub_text, _font())
        sub.setBrush(map_palette().text_muted)
        sub.setPos(x + PAD, y + _SUB_DY)

    def _draw_edge(self, start: QPointF, end: QPointF) -> None:
        self._scene.addLine(
            start.x(),
            start.y(),
            end.x(),
            end.y(),
            QPen(map_palette().edge, _EDGE_PEN_W),
        )
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        tip = QPointF(
            end.x() - TEAM_H / HALF * math.cos(angle),
            end.y() - TEAM_H / HALF * math.sin(angle),
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
            QPolygonF([tip, left, right]),
            QPen(map_palette().edge),
            QBrush(map_palette().edge),
        )
