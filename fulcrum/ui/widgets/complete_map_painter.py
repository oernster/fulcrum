"""Scene painting for the complete picture.

Draw functions for the complete map's domain boxes, team boxes, labels and
dependency edges. CompleteMapView owns navigation, hover and overlays and
calls in here; splitting the painting keeps both modules within the size
limit, mirroring org_map_painter beside OrgMapView.
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

from fulcrum.domain.hierarchy import headcount_in_domain, teams_in_domain
from fulcrum.domain.models import Domain, OrgState
from fulcrum.shared.text import count_noun
from fulcrum.ui.map_palette import map_palette
from fulcrum.ui.widgets.complete_map_edges import direct_is_clear, route_edges
from fulcrum.ui.widgets.complete_map_layout import (
    HALF,
    PAD,
    SHELL_DETAIL,
    SHELL_ID,
    SHELL_LABEL,
    TEAM_H,
    is_summary,
)

# Public: the view's hover ring wraps a box at this corner radius.
CORNER = 10.0
_PEN_W = 2
_ARROW = 9.0
_NAME_DY = 8.0
_SUB_DY = 31.0
_DOMAIN_CATEGORY_DY = 6.0
_DOMAIN_NAME_DY = 21.0
_DOMAIN_LEAD_DY = 38.0
_DOMAIN_ROLLUP_DY = 55.0
_FULL = 1.0
_EDGE_PEN_W = 1.5
# A hub's counted trunk draws slightly heavier than a single edge, so the
# merge reads as "many wires" at a glance.
_TRUNK_PEN_W = 2.5
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


def _domain(org: OrgState, ident: str) -> Domain:
    return next(domain for domain in org.domains if domain.id == ident)


def _elide(text: str, font: QFont, width: float) -> str:
    """Elide with an ellipsis so a detail line never spills its box."""
    return QFontMetricsF(font).elidedText(text, Qt.TextElideMode.ElideRight, width)


def draw_domain(
    scene: QGraphicsScene, org: OrgState, summarize: bool, x, y, box, claimed
) -> None:
    """One domain box, its border and detail rolling the subtree up.

    Any standing claim in the subtree reads contested (violet); otherwise
    the border blends from amber toward green with the share of member
    teams deciding locally. The detail line carries the counts themselves,
    so a change deep inside the unit (a delegation in one department of a
    contested division) is visible as numbers even where the border colour
    cannot move.
    """
    if box.ident == SHELL_ID:
        _draw_shell(scene, x, y, box)
        return
    domain = _domain(org, box.ident)
    members = teams_in_domain(org, domain.id)
    contested_count = sum(1 for team in members if team.id in claimed)
    held = sum(1 for team in members if team.has_local_authority)
    if contested_count:
        border = map_palette().contested
    elif not members:
        border = map_palette().no_authority
    else:
        border = _blend(
            map_palette().no_authority, map_palette().authority, held / len(members)
        )
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, y, box.w, box.h), CORNER, CORNER)
    scene.addPath(path, QPen(border, _PEN_W), QBrush(map_palette().domain_fill))
    people = headcount_in_domain(org, domain.id)
    detail = f"{domain.category} · {count_noun(people, 'person', 'people')}"
    if is_summary(domain, summarize):
        detail = f"{detail} · {count_noun(len(members), 'team')}"
    category = scene.addSimpleText(_elide(detail, _font(), box.w - PAD * HALF), _font())
    category.setBrush(border)
    category.setPos(x + PAD, y + _DOMAIN_CATEGORY_DY)
    name = scene.addSimpleText(domain.name, _font(bold=True))
    name.setBrush(map_palette().text)
    name.setPos(x + PAD, y + _DOMAIN_NAME_DY)
    if domain.lead:
        lead = scene.addSimpleText(f"lead: {domain.lead}", _font())
        lead.setBrush(map_palette().text_muted)
        lead.setPos(x + PAD, y + _DOMAIN_LEAD_DY)
    if members:
        # The rollup gets its own line, numbers first, so elision can never
        # swallow the part that changes between two positions.
        rollup = f"{held}/{len(members)} decide locally"
        if contested_count:
            rollup = f"{held}/{len(members)} decide · {contested_count} contested"
        line = scene.addSimpleText(_elide(rollup, _font(), box.w - PAD * HALF), _font())
        line.setBrush(border)
        line.setPos(x + PAD, y + _DOMAIN_ROLLUP_DY)


def _draw_shell(scene: QGraphicsScene, x, y, box) -> None:
    """The synthetic Shell: dashed and muted, visibly not modelled."""
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, y, box.w, box.h), CORNER, CORNER)
    pen = QPen(map_palette().text_muted, _PEN_W)
    pen.setDashPattern(_SHELL_DASH)
    scene.addPath(path, pen, QBrush(Qt.BrushStyle.NoBrush))
    name = scene.addSimpleText(SHELL_LABEL, _font(bold=True))
    name.setBrush(map_palette().text_muted)
    name.setPos(x + PAD, y + _DOMAIN_NAME_DY)
    detail = scene.addSimpleText(SHELL_DETAIL, _font())
    detail.setBrush(map_palette().text_muted)
    detail.setPos(x + PAD, y + _DOMAIN_CATEGORY_DY)


def draw_team(scene: QGraphicsScene, org: OrgState, x, y, box, claimed) -> None:
    team = org.team(box.ident)
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, y, box.w, box.h), CORNER, CORNER)
    contested = team.id in claimed
    if contested:
        border = map_palette().contested
    else:
        ratio = _FULL if team.has_local_authority else 0.0
        border = _blend(map_palette().no_authority, map_palette().authority, ratio)
    scene.addPath(path, QPen(border, _PEN_W), QBrush(map_palette().team_fill))
    name = scene.addSimpleText(team.name, _font(bold=True))
    name.setBrush(map_palette().text)
    name.setPos(x + PAD, y + _NAME_DY)
    if contested:
        status = "contested"
    elif team.has_local_authority:
        status = "decides locally"
    else:
        status = "escalates"
    sub_text = f"{status} · {count_noun(team.headcount, 'person', 'people')}"
    sub = scene.addSimpleText(sub_text, _font())
    sub.setBrush(map_palette().text_muted)
    sub.setPos(x + PAD, y + _SUB_DY)


def draw_edges(scene: QGraphicsScene, org: OrgState, rects: dict[str, QRectF]) -> None:
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
    for dep in org.dependencies:
        if dep.upstream not in rects or dep.downstream not in rects:
            continue
        source, target = rects[dep.upstream], rects[dep.downstream]
        if direct_is_clear(source, target, rects):
            _draw_edge(scene, source.center(), target.center())
            continue
        routed.append((dep.upstream, dep.downstream))
    drawing = route_edges(tuple(routed), rects, diagram_right)
    for path, is_trunk in drawing.paths:
        width = _TRUNK_PEN_W if is_trunk else _EDGE_PEN_W
        scene.addPath(path, QPen(map_palette().edge, width))
    for arrow in drawing.arrows:
        scene.addPolygon(arrow, QPen(map_palette().edge), QBrush(map_palette().edge))
    for text, position in drawing.labels:
        label = scene.addSimpleText(text, _font(bold=True))
        label.setBrush(map_palette().text_muted)
        label.setPos(position)


def _draw_edge(scene: QGraphicsScene, start: QPointF, end: QPointF) -> None:
    scene.addLine(
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
    scene.addPolygon(
        QPolygonF([tip, left, right]),
        QPen(map_palette().edge),
        QBrush(map_palette().edge),
    )
