"""Edge routing for the complete picture: no line drawn through a box.

A dependency whose straight centre line crosses no other box keeps it. Any
other edge leaves its source's right side, runs down a lane to the right of
the whole diagram and enters its target's right side. A box fans its
connections along its edge so parallel runs never overlap, horizontal runs
hop crossed lanes with a small semicircle and a hub (a box with more routed
connections than its edge can present) merges them into one counted trunk
per direction on a shared lane, so neither the box edge nor the lane gutter
ever drowns in lines.
"""

from __future__ import annotations

from dataclasses import dataclass

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
# far apart; when a box has more connections than its edge can hold at this
# spacing, the fan compresses to fit between the corner margins.
_FAN_STEP = 12.0
_FAN_MARGIN = 12.0
# Routed edges run down lanes beyond the widest box: the first lane sits
# this far out and each further lane steps outward.
_LANE_BASE = 36.0
_LANE_STEP = 22.0
# Above this many routed connections a box is a hub: each direction merges
# into one counted trunk on one shared lane instead of a line per edge.
_TRUNK_THRESHOLD = 8
_LABEL_DX = 14.0
# The inbound count sits above its stub and the outbound count below its
# own, so a hub carrying both never overlaps the two labels.
_LABEL_ABOVE_DY = 20.0
_LABEL_BELOW_DY = 6.0

_SOURCE = 0
_TARGET = 1
_GROUP_IN = "in"
_GROUP_OUT = "out"
_GROUP_SINGLE = "single"


@dataclass(frozen=True, slots=True)
class EdgeDrawing:
    """Everything the view draws for the routed edges: paths flagged as
    trunk or not, arrow heads and the hubs' count labels."""

    paths: tuple[tuple[QPainterPath, bool], ...]
    arrows: tuple[QPolygonF, ...]
    labels: tuple[tuple[str, QPointF], ...]


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


def direct_is_clear(source: QRectF, target: QRectF, rects: dict[str, QRectF]) -> bool:
    """Whether the centre line touches no box beyond the endpoints' own.

    Only a box that contains a whole endpoint box (itself, or an ancestor:
    the nesting means an edge must cross its own container borders) is
    excused; anything else can veto the line. Containing just the endpoint
    POINT is not enough, since a child box can contain its parent's centre
    and a line through a child is exactly what routing exists to prevent.
    """
    segment = QLineF(source.center(), target.center())
    for rect in rects.values():
        if rect.contains(source) or rect.contains(target):
            continue
        if _crosses(segment, rect):
            return False
    return True


def _fan_anchors(pairs, rects, skip) -> list[list[float]]:
    """One [source_y, target_y] per pair, fanned along each box's edge.

    Attachments are ordered by where their counterpart sits, so the run to
    a higher counterpart leaves higher and neighbouring runs never swap
    over right at the box. Hub-side attachments (in skip) are left for the
    trunk stubs to place.
    """
    attachments: dict[str, list[tuple[int, int, float]]] = {}
    for index, (source_id, target_id) in enumerate(pairs):
        if (index, _SOURCE) not in skip:
            counterpart_y = rects[target_id].center().y()
            attachments.setdefault(source_id, []).append(
                (index, _SOURCE, counterpart_y)
            )
        if (index, _TARGET) not in skip:
            source_y = rects[source_id].center().y()
            attachments.setdefault(target_id, []).append((index, _TARGET, source_y))
    anchors = [[rects[s].center().y(), rects[t].center().y()] for s, t in pairs]
    for ident, items in attachments.items():
        rect = rects[ident]
        items.sort(key=lambda item: item[2])
        count = len(items)
        usable = max(rect.height() - _FAN_MARGIN * _HALF, 0.0)
        step = _FAN_STEP if count == 1 else min(_FAN_STEP, usable / (count - 1))
        start = rect.center().y() - step * (count - 1) / _HALF
        for slot, (index, role, _) in enumerate(items):
            anchors[index][role] = start + slot * step
    return anchors


def _hop_crossings(y, x_from, x_to, verticals) -> list[float]:
    """The x positions where this horizontal run crosses another lane,
    ordered along the direction of travel; endpoint touches are junctions
    of the same route family, not crossings, so only strict interiors count."""
    low, high = min(x_from, x_to), max(x_from, x_to)
    crossed = [
        x for (x, y_low, y_high) in verticals if low < x < high and y_low < y < y_high
    ]
    return sorted(crossed, reverse=x_from > x_to)


def _horizontal_run(path: QPainterPath, x_to: float, verticals) -> None:
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


def _arrow_at(rect: QRectF, y: float) -> QPolygonF:
    """An arrow head entering the box's right edge, pointing left."""
    tip = QPointF(rect.right(), y)
    return QPolygonF(
        [
            tip,
            QPointF(tip.x() + _ARROW, tip.y() - _ARROW_HALF_SPAN),
            QPointF(tip.x() + _ARROW, tip.y() + _ARROW_HALF_SPAN),
        ]
    )


class _Router:
    """One routing pass: groups hub edges, assigns lanes, emits drawables."""

    def __init__(self, pairs, rects, diagram_right) -> None:
        self._pairs = pairs
        self._rects = rects
        counts: dict[str, int] = {}
        for source_id, target_id in pairs:
            counts[source_id] = counts.get(source_id, 0) + 1
            counts[target_id] = counts.get(target_id, 0) + 1
        self._hubs = {i for i, c in counts.items() if c > _TRUNK_THRESHOLD}
        self._keys = [self._key(i, p) for i, p in enumerate(pairs)]
        skip = {
            (i, role)
            for i, (s, t) in enumerate(pairs)
            for role, ident in ((_SOURCE, s), (_TARGET, t))
            if ident in self._hubs
        }
        self._anchors = _fan_anchors(pairs, rects, skip)
        self._place_hub_stubs()
        self._lanes: dict[tuple, float] = {}
        for key in self._keys:
            if key not in self._lanes:
                self._lanes[key] = (
                    diagram_right + _LANE_BASE + len(self._lanes) * _LANE_STEP
                )
        spans: dict[tuple, list[float]] = {}
        for index, key in enumerate(self._keys):
            spans.setdefault(key, []).extend(self._anchors[index])
        self._verticals = {
            key: (self._lanes[key], min(ys), max(ys)) for key, ys in spans.items()
        }

    def _key(self, index: int, pair: tuple[str, str]) -> tuple:
        source_id, target_id = pair
        if target_id in self._hubs:
            return (_GROUP_IN, target_id)
        if source_id in self._hubs:
            return (_GROUP_OUT, source_id)
        return (_GROUP_SINGLE, index)

    def _place_hub_stubs(self) -> None:
        """Each hub gets one stub y per direction, offset when both exist."""
        self._stub_in: dict[str, float] = {}
        self._stub_out: dict[str, float] = {}
        for ident in self._hubs:
            centre = self._rects[ident].center().y()
            has_in = any(t == ident for _, t in self._pairs)
            has_out = any(s == ident for s, _ in self._pairs)
            offset = _FAN_STEP / _HALF if (has_in and has_out) else 0.0
            self._stub_in[ident] = centre - offset
            self._stub_out[ident] = centre + offset
        for index, (source_id, target_id) in enumerate(self._pairs):
            if source_id in self._hubs:
                self._anchors[index][_SOURCE] = self._stub_out[source_id]
            if target_id in self._hubs:
                self._anchors[index][_TARGET] = self._stub_in[target_id]

    def _others(self, key: tuple):
        return tuple(v for k, v in self._verticals.items() if k != key)

    def build(self) -> EdgeDrawing:
        paths: list[tuple[QPainterPath, bool]] = []
        arrows: list[QPolygonF] = []
        labels: list[tuple[str, QPointF]] = []
        drawn: set[tuple] = set()
        for index, (source_id, target_id) in enumerate(self._pairs):
            key = self._keys[index]
            lane_x = self._lanes[key]
            source_y, target_y = self._anchors[index]
            source, target = self._rects[source_id], self._rects[target_id]
            if key[0] == _GROUP_SINGLE:
                path = QPainterPath(QPointF(source.right(), source_y))
                _horizontal_run(path, lane_x, self._others(key))
                path.lineTo(lane_x, target_y)
                _horizontal_run(path, target.right() + _ARROW, self._others(key))
                paths.append((path, False))
                arrows.append(_arrow_at(target, target_y))
                continue
            if key[0] == _GROUP_IN:
                # The member's run merges into the shared lane; the trunk
                # below carries the single counted entry into the hub.
                path = QPainterPath(QPointF(source.right(), source_y))
                _horizontal_run(path, lane_x, self._others(key))
                paths.append((path, False))
            else:
                path = QPainterPath(QPointF(lane_x, target_y))
                _horizontal_run(path, target.right() + _ARROW, self._others(key))
                paths.append((path, False))
                arrows.append(_arrow_at(target, target_y))
            if key not in drawn:
                drawn.add(key)
                self._emit_trunk(key, paths, arrows, labels)
        return EdgeDrawing(tuple(paths), tuple(arrows), tuple(labels))

    def _emit_trunk(self, key: tuple, paths, arrows, labels) -> None:
        kind, hub_id = key
        hub = self._rects[hub_id]
        lane_x, y_low, y_high = self._verticals[key]
        stub_y = self._stub_in[hub_id] if kind == _GROUP_IN else self._stub_out[hub_id]
        trunk = QPainterPath(QPointF(lane_x, y_low))
        trunk.lineTo(lane_x, y_high)
        paths.append((trunk, True))
        stub = QPainterPath(QPointF(lane_x, stub_y))
        if kind == _GROUP_IN:
            _horizontal_run(stub, hub.right() + _ARROW, self._others(key))
            arrows.append(_arrow_at(hub, stub_y))
        else:
            _horizontal_run(stub, hub.right(), self._others(key))
        paths.append((stub, True))
        count = sum(1 for k in self._keys if k == key)
        label_y = (
            stub_y - _LABEL_ABOVE_DY if kind == _GROUP_IN else stub_y + _LABEL_BELOW_DY
        )
        labels.append((f"× {count}", QPointF(hub.right() + _LABEL_DX, label_y)))


def route_edges(
    pairs: tuple[tuple[str, str], ...],
    rects: dict[str, QRectF],
    diagram_right: float,
) -> EdgeDrawing:
    """Route every non-direct edge; see the module docstring for the rules."""
    if not pairs:
        return EdgeDrawing((), (), ())
    return _Router(pairs, rects, diagram_right).build()
