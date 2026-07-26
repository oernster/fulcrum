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
# Where a horizontal run crosses another edge's vertical lane, the
# horizontal hops over it with a small semicircle, the circuit-diagram
# convention for "these wires do not meet". Verticals stay plain.
_HOP_R = 4.0
_TOP_HALF_START = 180.0
_TOP_HALF_SWEEP = -180.0
_TOP_HALF_START_BACK = 0.0
_TOP_HALF_SWEEP_BACK = 180.0
# A box with several connections fans them out along its right edge, this
# far apart, so parallel runs never overlap; when a box has more
# connections than its edge can hold at this spacing, the fan compresses
# to fit between the corner margins.
_FAN_STEP = 12.0
_FAN_MARGIN = 12.0


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


def fan_anchors(
    pairs: tuple[tuple[str, str], ...], rects: dict[str, QRectF]
) -> tuple[tuple[float, float], ...]:
    """One (source_y, target_y) per routed pair, fanned along each box edge.

    Every box's attachments are ordered by where their counterpart sits, so
    the fan follows the geometry (the run to a higher counterpart leaves
    higher) and neighbouring runs never swap over right at the box.
    """
    attachments: dict[str, list[tuple[int, int, float]]] = {}
    for index, (source_id, target_id) in enumerate(pairs):
        counterpart_y = rects[target_id].center().y()
        attachments.setdefault(source_id, []).append((index, 0, counterpart_y))
        source_y = rects[source_id].center().y()
        attachments.setdefault(target_id, []).append((index, 1, source_y))
    anchors = [[0.0, 0.0] for _ in pairs]
    for ident, items in attachments.items():
        rect = rects[ident]
        items.sort(key=lambda item: item[2])
        count = len(items)
        usable = max(rect.height() - _FAN_MARGIN * _HALF, 0.0)
        step = _FAN_STEP if count == 1 else min(_FAN_STEP, usable / (count - 1))
        start = rect.center().y() - step * (count - 1) / _HALF
        for slot, (index, role, _) in enumerate(items):
            anchors[index][role] = start + slot * step
    return tuple((source_y, target_y) for source_y, target_y in anchors)


def _hop_crossings(
    y: float,
    x_from: float,
    x_to: float,
    verticals: tuple[tuple[float, float, float], ...],
) -> list[float]:
    """The x positions where this horizontal run crosses another lane,
    ordered along the direction of travel; endpoint touches are junctions
    of the same route family, not crossings, so only strict interiors count."""
    low, high = min(x_from, x_to), max(x_from, x_to)
    crossed = [
        x for (x, y_low, y_high) in verticals if low < x < high and y_low < y < y_high
    ]
    return sorted(crossed, reverse=x_from > x_to)


def _horizontal_run(
    path: QPainterPath,
    x_to: float,
    verticals: tuple[tuple[float, float, float], ...],
) -> None:
    """Extend the path horizontally, hopping over any crossed lane."""
    x_from = path.currentPosition().x()
    y = path.currentPosition().y()
    going_right = x_to > x_from
    for cx in _hop_crossings(y, x_from, x_to, verticals):
        path.lineTo(cx - _HOP_R if going_right else cx + _HOP_R, y)
        bump = QRectF(cx - _HOP_R, y - _HOP_R, _HOP_R * _HALF, _HOP_R * _HALF)
        if going_right:
            path.arcTo(bump, _TOP_HALF_START, _TOP_HALF_SWEEP)
        else:
            path.arcTo(bump, _TOP_HALF_START_BACK, _TOP_HALF_SWEEP_BACK)
    path.lineTo(x_to, y)


def lane_path(
    source: QRectF,
    target: QRectF,
    lane_x: float,
    source_y: float,
    target_y: float,
    verticals: tuple[tuple[float, float, float], ...] = (),
) -> QPainterPath:
    """Right-angled route: out of the source's side, down the lane, into the
    target's side, stopping where the arrow head takes over. The y anchors
    come from fan_anchors; verticals are the OTHER routed edges' lanes as
    (x, y_low, y_high) and the horizontal runs hop over any they cross."""
    path = QPainterPath(QPointF(source.right(), source_y))
    _horizontal_run(path, lane_x, verticals)
    path.lineTo(lane_x, target_y)
    _horizontal_run(path, target.right() + _ARROW, verticals)
    return path


def lane_arrow(target: QRectF, target_y: float) -> QPolygonF:
    """An arrow head entering the target's right edge, pointing left."""
    tip = QPointF(target.right(), target_y)
    return QPolygonF(
        [
            tip,
            QPointF(tip.x() + _ARROW, tip.y() - _ARROW_HALF_SPAN),
            QPointF(tip.x() + _ARROW, tip.y() + _ARROW_HALF_SPAN),
        ]
    )
