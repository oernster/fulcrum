"""Edge routing for the complete picture: no line drawn through a box.

A dependency whose straight centre line crosses no other box keeps it. Any
other edge leaves its source's right side, runs down a clear lane to the
right of the whole diagram and enters its target's right side, so the tree
stays readable however the boxes stack. Each routed edge gets its own lane
offset, keeping parallel routes apart.
"""

from __future__ import annotations

from PySide6.QtCore import QLineF, QPointF, QRectF
from PySide6.QtGui import QPainterPath, QPolygonF

_HALF = 2.0
_ARROW = 9.0
_ARROW_HALF_SPAN = 5.4


def _crosses(segment: QLineF, rect: QRectF) -> bool:
    if rect.contains(segment.p1()) and rect.contains(segment.p2()):
        return True
    corners = (
        rect.topLeft(),
        rect.topRight(),
        rect.bottomRight(),
        rect.bottomLeft(),
    )
    for index in range(len(corners)):
        side = QLineF(corners[index], corners[(index + 1) % len(corners)])
        kind, _ = segment.intersects(side)
        if kind == QLineF.IntersectionType.BoundedIntersection:
            return True
    return False


def direct_is_clear(start: QPointF, end: QPointF, rects: dict[str, QRectF]) -> bool:
    """Whether the straight line touches no box beyond the endpoints' own.

    A box containing either endpoint is the source, the target or one of
    their ancestors (the nesting means an edge must cross its own container
    borders), so only boxes containing neither endpoint can veto the line.
    """
    segment = QLineF(start, end)
    for rect in rects.values():
        if rect.contains(start) or rect.contains(end):
            continue
        if _crosses(segment, rect):
            return False
    return True


def lane_path(source: QRectF, target: QRectF, lane_x: float) -> QPainterPath:
    """Right-angled route: out of the source's side, down the lane, into the
    target's side, stopping where the arrow head takes over."""
    source_y = source.center().y()
    target_y = target.center().y()
    path = QPainterPath(QPointF(source.right(), source_y))
    path.lineTo(lane_x, source_y)
    path.lineTo(lane_x, target_y)
    path.lineTo(target.right() + _ARROW, target_y)
    return path


def lane_arrow(target: QRectF) -> QPolygonF:
    """An arrow head entering the target's right edge, pointing left."""
    tip = QPointF(target.right(), target.center().y())
    return QPolygonF(
        [
            tip,
            QPointF(tip.x() + _ARROW, tip.y() - _ARROW_HALF_SPAN),
            QPointF(tip.x() + _ARROW, tip.y() + _ARROW_HALF_SPAN),
        ]
    )
