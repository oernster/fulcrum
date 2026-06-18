"""A single complete picture of the whole organisation.

Domains are drawn as nested boxes holding their teams and sub-domains, with
every dependency drawn between the teams. It complements the drill-down map by
showing the entire structure at once rather than one level at a time. Layout is
a simple recursive flow: each domain sizes to fit its children, wrapping after a
few per row, and the teams are leaves.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
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

from fulcrum.domain.hierarchy import child_domains, root_domains, teams_in_domain
from fulcrum.domain.models import Domain, OrgState

_AUTHORITY = QColor("#34d399")
_NO_AUTHORITY = QColor("#f59e0b")
_TEAM_FILL = QColor("#1a1e24")
_DOMAIN_FILL = QColor("#222831")
_TEXT = QColor("#e6e9ee")
_TEXT_MUTED = QColor("#9aa3af")
_EDGE = QColor("#5b6470")
_BG = QColor("#0d0f12")

_KIND_TEAM = "team"
_KIND_DOMAIN = "domain"
_TEAM_W = 170.0
_TEAM_H = 58.0
_HEADER_H = 56.0
_PAD = 14.0
_GAP = 16.0
_PER_ROW = 3
_CORNER = 10.0
_PEN_W = 2
_HALF = 2.0
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


class _Box:
    """A laid-out node: a team leaf, or a domain holding positioned children."""

    __slots__ = ("kind", "ident", "w", "h", "children")

    def __init__(self, kind, ident, w, h, children) -> None:
        self.kind = kind
        self.ident = ident
        self.w = w
        self.h = h
        self.children = children


def _flow(boxes: list[_Box]) -> tuple[list[tuple[float, float, _Box]], float, float]:
    """Pack boxes into rows of _PER_ROW; return (placed, width, height)."""
    placed: list[tuple[float, float, _Box]] = []
    x = y = row_h = right = 0.0
    for index, box in enumerate(boxes):
        if index and index % _PER_ROW == 0:
            x = 0.0
            y += row_h + _GAP
            row_h = 0.0
        placed.append((x, y, box))
        right = max(right, x + box.w)
        x += box.w + _GAP
        row_h = max(row_h, box.h)
    return placed, right, y + row_h


class CompleteMapView(QGraphicsView):
    """Draws the whole org at once: nested domain boxes, teams and all edges."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(_BG))
        self._org: OrgState | None = None

    def set_org(self, org: OrgState) -> None:
        self._org = org
        self._render()
        self.fit_to_contents()

    def fit_to_contents(self) -> None:
        bounds = self._scene.itemsBoundingRect()
        if not bounds.isEmpty():
            self.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = _ZOOM_STEP if delta > 0 else _FULL / _ZOOM_STEP
        target = self.transform().m11() * factor
        if _MIN_SCALE <= target <= _MAX_SCALE:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self.scale(factor, factor)

    def _measure(self, kind: str, ident: str) -> _Box:
        if kind == _KIND_TEAM:
            return _Box(_KIND_TEAM, ident, _TEAM_W, _TEAM_H, [])
        children = [
            self._measure(_KIND_DOMAIN, domain.id)
            for domain in child_domains(self._org, ident)
        ]
        children += [
            self._measure(_KIND_TEAM, team.id)
            for team in teams_in_domain(self._org, ident, recursive=False)
        ]
        placed, inner_w, inner_h = _flow(children)
        offset = [(_PAD + rx, _HEADER_H + ry, box) for (rx, ry, box) in placed]
        width = max(inner_w + _PAD * _HALF, _TEAM_W + _PAD * _HALF)
        height = _HEADER_H + inner_h + _PAD
        return _Box(_KIND_DOMAIN, ident, width, height, offset)

    def _render(self) -> None:
        self._scene.clear()
        if self._org is None:
            return
        roots = [
            self._measure(_KIND_DOMAIN, domain.id) for domain in root_domains(self._org)
        ]
        roots += [
            self._measure(_KIND_TEAM, team.id)
            for team in self._org.teams
            if team.domain_id is None
        ]
        placed, _, _ = _flow(roots)
        centers: dict[str, QPointF] = {}
        domains: list[tuple[float, float, _Box]] = []
        teams: list[tuple[float, float, _Box]] = []
        for rx, ry, box in placed:
            self._collect(box, rx, ry, centers, domains, teams)
        for x, y, box in domains:
            self._draw_domain(x, y, box)
        for x, y, box in teams:
            self._draw_team(x, y, box)
        for dep in self._org.dependencies:
            if dep.upstream in centers and dep.downstream in centers:
                self._draw_edge(centers[dep.upstream], centers[dep.downstream])

    def _collect(self, box, x, y, centers, domains, teams) -> None:
        if box.kind == _KIND_TEAM:
            teams.append((x, y, box))
            centers[box.ident] = QPointF(x + box.w / _HALF, y + box.h / _HALF)
            return
        domains.append((x, y, box))
        for rx, ry, child in box.children:
            self._collect(child, x + rx, y + ry, centers, domains, teams)

    def _domain(self, ident: str) -> Domain:
        return next(domain for domain in self._org.domains if domain.id == ident)

    def _draw_domain(self, x, y, box) -> None:
        domain = self._domain(box.ident)
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, box.w, box.h), _CORNER, _CORNER)
        self._scene.addPath(path, QPen(_NO_AUTHORITY, _PEN_W), QBrush(_DOMAIN_FILL))
        category = self._scene.addSimpleText(domain.category, _font())
        category.setBrush(_NO_AUTHORITY)
        category.setPos(x + _PAD, y + _DOMAIN_CATEGORY_DY)
        name = self._scene.addSimpleText(domain.name, _font(bold=True))
        name.setBrush(_TEXT)
        name.setPos(x + _PAD, y + _DOMAIN_NAME_DY)
        if domain.lead:
            lead = self._scene.addSimpleText(f"lead: {domain.lead}", _font())
            lead.setBrush(_TEXT_MUTED)
            lead.setPos(x + _PAD, y + _DOMAIN_LEAD_DY)

    def _draw_team(self, x, y, box) -> None:
        team = self._org.team(box.ident)
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, box.w, box.h), _CORNER, _CORNER)
        ratio = _FULL if team.has_local_authority else 0.0
        border = _blend(_NO_AUTHORITY, _AUTHORITY, ratio)
        self._scene.addPath(path, QPen(border, _PEN_W), QBrush(_TEAM_FILL))
        name = self._scene.addSimpleText(team.name, _font(bold=True))
        name.setBrush(_TEXT)
        name.setPos(x + _PAD, y + _NAME_DY)
        status = "decides locally" if team.has_local_authority else "escalates"
        sub = self._scene.addSimpleText(status, _font())
        sub.setBrush(_TEXT_MUTED)
        sub.setPos(x + _PAD, y + _SUB_DY)

    def _draw_edge(self, start: QPointF, end: QPointF) -> None:
        self._scene.addLine(start.x(), start.y(), end.x(), end.y(), QPen(_EDGE, 1.5))
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        tip = QPointF(
            end.x() - _TEAM_H / _HALF * math.cos(angle),
            end.y() - _TEAM_H / _HALF * math.sin(angle),
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
