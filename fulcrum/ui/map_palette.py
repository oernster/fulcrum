"""The map canvas colours, resolved per theme.

The board and the complete picture paint their own colours rather than
reading QSS, so they carry their own palette pair. set_map_theme flips the
module's current palette; the views rebuild their scenes on the next
refresh, which is how a theme switch repaints the board. The authority
encoding keeps its meaning in both themes: green decides locally, amber
escalates, violet is contested (violet rather than red, so the state stays
distinct from the green hover ring under red-green colour blindness and
never reads as an error); only the depth changes so each reads on its
surface.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor

from fulcrum.ui.theme_palettes import DEFAULT_THEME, THEME_LIGHT


@dataclass(frozen=True, slots=True)
class MapPalette:
    """The colour tokens the map painters resolve."""

    bg: QColor
    team_fill: QColor
    domain_fill: QColor
    text: QColor
    text_muted: QColor
    edge: QColor
    authority: QColor
    no_authority: QColor
    contested: QColor
    ring: QColor
    preview: QColor


DARK_MAP = MapPalette(
    bg=QColor("#0d0f12"),
    team_fill=QColor("#1a1e24"),
    domain_fill=QColor("#222831"),
    text=QColor("#e6e9ee"),
    text_muted=QColor("#9aa3af"),
    edge=QColor("#5b6470"),
    authority=QColor("#34d399"),
    no_authority=QColor("#f59e0b"),
    contested=QColor("#a855f7"),
    ring=QColor("#2f9e64"),
    preview=QColor("#fbbf24"),
)

LIGHT_MAP = MapPalette(
    bg=QColor("#e9edf2"),
    team_fill=QColor("#ffffff"),
    domain_fill=QColor("#dde3eb"),
    text=QColor("#1a1e24"),
    text_muted=QColor("#5b6470"),
    edge=QColor("#8a94a4"),
    authority=QColor("#059669"),
    no_authority=QColor("#d97706"),
    contested=QColor("#7c3aed"),
    ring=QColor("#15803d"),
    preview=QColor("#b45309"),
)

_current: MapPalette = DARK_MAP if DEFAULT_THEME != THEME_LIGHT else LIGHT_MAP


def set_map_theme(theme: str) -> None:
    """Flip the current map palette; views repaint on their next rebuild."""
    global _current
    _current = LIGHT_MAP if theme == THEME_LIGHT else DARK_MAP


def map_palette() -> MapPalette:
    """The palette the painters resolve at draw time."""
    return _current
