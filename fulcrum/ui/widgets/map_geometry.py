"""Where an edge meets a box, and the arrow head that sits there.

Shared by both map painters so a dependency is drawn the same way on the
drill map and on the complete picture. A centre-to-centre line drawn without
this runs out through the body of its own source box and its arrow head
lands wherever the trigonometry happens to put it, which is right only when
the approach is exactly horizontal or exactly vertical.

Pure geometry: no scene, no palette, no Qt widgets.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPolygonF

_HALF = 2.0
_ARROW_SPREAD = math.pi / 6


def border_point(rect: QRectF, angle: float) -> QPointF:
    """Where a ray leaving the rect's centre at ``angle`` crosses its border.

    The ray is scaled by whichever axis it runs out of first, so the result
    sits on the edge for every direction rather than only on the two axes.
    """
    centre = rect.center()
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    reach_x = abs(rect.width() / _HALF / cos_a) if cos_a else math.inf
    reach_y = abs(rect.height() / _HALF / sin_a) if sin_a else math.inf
    reach = min(reach_x, reach_y)
    if not math.isfinite(reach):
        return QPointF(centre)
    return QPointF(centre.x() + reach * cos_a, centre.y() + reach * sin_a)


def edge_span(source: QRectF, target: QRectF) -> tuple[QPointF, QPointF, float] | None:
    """The visible run between two boxes: border to border, plus its angle.

    None when the boxes touch or overlap, where there is no gap to draw in
    and a line would be painted backwards through both of them.
    """
    start = source.center()
    end = target.center()
    dx = end.x() - start.x()
    dy = end.y() - start.y()
    if not dx and not dy:
        return None
    angle = math.atan2(dy, dx)
    from_edge = border_point(source, angle)
    to_edge = border_point(target, angle + math.pi)
    run_x = to_edge.x() - from_edge.x()
    run_y = to_edge.y() - from_edge.y()
    if run_x * dx + run_y * dy <= 0:
        return None
    return from_edge, to_edge, angle


def arrow_head(tip: QPointF, angle: float, size: float) -> QPolygonF:
    """A filled head whose point sits exactly on ``tip``, aimed along ``angle``."""
    return QPolygonF(
        [
            tip,
            QPointF(
                tip.x() - size * math.cos(angle - _ARROW_SPREAD),
                tip.y() - size * math.sin(angle - _ARROW_SPREAD),
            ),
            QPointF(
                tip.x() - size * math.cos(angle + _ARROW_SPREAD),
                tip.y() - size * math.sin(angle + _ARROW_SPREAD),
            ),
        ]
    )
