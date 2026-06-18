"""UI scaling helper.

The composition root sets the factor once at startup from the screen height;
widgets read it through px(). Kept in the UI layer, never in the domain.
"""

from __future__ import annotations

_DEFAULT_FACTOR = 1.0
_MIN_FACTOR = 0.5
_state = {"factor": _DEFAULT_FACTOR}


def init(factor: float) -> None:
    _state["factor"] = max(_MIN_FACTOR, factor)


def factor() -> float:
    return _state["factor"]


def px(value: float) -> int:
    return int(round(value * _state["factor"]))
