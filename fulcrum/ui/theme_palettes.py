"""The semantic colour palettes the stylesheet builds from.

One frozen palette per theme; amber stays the meaning colour in both and
only its depth changes so it reads on each surface.
"""

from __future__ import annotations

from dataclasses import dataclass

THEME_DARK = "dark"
THEME_LIGHT = "light"
DEFAULT_THEME = THEME_DARK


@dataclass(frozen=True, slots=True)
class _Palette:
    """The semantic colour tokens one theme resolves.

    divider is the one standard divider colour: every splitter bar and both
    scrollbar orientations use it, so no divider-like line drifts. ring_green
    marks an enabled control under the mouse or holding keyboard focus;
    ring_red marks any disabled control, permanently, so unavailable is
    visible. Amber stays the meaning colour in both themes. growth is the
    guide's growth accent: the grow toggle wears it when on and the rows
    whose line growth changes wear the same colour, so where growth has any
    effect is visible at a glance; blue, so it never reads as a ring or as
    the amber meaning colour.
    """

    bg: str
    surface: str
    surface_raised: str
    border: str
    text: str
    text_muted: str
    accent: str
    accent_bright: str
    disabled_text: str
    divider: str
    ring_green: str
    ring_red: str
    growth: str


DARK = _Palette(
    bg="#0d0f12",
    surface="#1a1e24",
    surface_raised="#222831",
    border="#2c333d",
    text="#e6e9ee",
    text_muted="#9aa3af",
    accent="#f59e0b",
    accent_bright="#fbbf24",
    disabled_text="#5b6470",
    divider="#9aa3af",
    ring_green="#22c55e",
    ring_red="#ef4444",
    growth="#3b82f6",
)

# The light palette keeps amber as the meaning colour, darkened so it reads
# as text on a light surface, with the rings deepened for the same reason.
LIGHT = _Palette(
    bg="#f2f4f7",
    surface="#ffffff",
    surface_raised="#e7ebf0",
    border="#c6cfda",
    text="#1a1e24",
    text_muted="#5b6470",
    accent="#d97706",
    accent_bright="#b45309",
    disabled_text="#9aa3af",
    divider="#b3bdc9",
    ring_green="#15803d",
    ring_red="#dc2626",
    growth="#1d4ed8",
)

PALETTES = {THEME_DARK: DARK, THEME_LIGHT: LIGHT}
