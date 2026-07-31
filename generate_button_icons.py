#!/usr/bin/env python3
"""Generate the header-button icons into assets/buttons.

Three glyphs drawn in the app palette on transparent backgrounds: an org
tree with an amber root (Model my organisation), that tree under an amber
pencil with a blue inner stripe and a red tip (Edit my org) and grey steps
climbed by an amber arrow (Show the guide). Each icon is emitted at the
sizes the main window's QIcon loads, so buttons stay crisp at every UI
scale. Deterministic: rerunning writes identical files.

Run from the repository root:

    python generate_button_icons.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "assets" / "buttons"

_SCALE = 2
_CANVAS = 1024 * _SCALE
_SIZES = (32, 64, 256)

_TEXT = "#e6e9ee"
_MUTED = "#9aa3af"
_ACCENT = "#f59e0b"
_BLUE = "#60a5fa"
_RED = "#ef4444"


def _s(*vals: float) -> list[float]:
    return [v * _SCALE for v in vals]


def _canvas() -> Image.Image:
    return Image.new("RGBA", (_CANVAS, _CANVAS), (0, 0, 0, 0))


def _elbow(d: ImageDraw.ImageDraw, x0, y0, x1, y1, colour, width) -> None:
    midy = (y0 + y1) // 2
    d.line(_s(x0, y0, x0, midy), fill=colour, width=width * _SCALE)
    d.line(
        _s(min(x0, x1) - width // 2, midy, max(x0, x1) + width // 2, midy),
        fill=colour,
        width=width * _SCALE,
    )
    d.line(_s(x1, midy, x1, y1), fill=colour, width=width * _SCALE)


def _circle(d: ImageDraw.ImageDraw, cx, cy, r, outline=None, fill=None, width=0):
    d.ellipse(
        _s(cx - r, cy - r, cx + r, cy + r),
        outline=outline,
        fill=fill,
        width=width * _SCALE,
    )


def _unit(x0, y0, x1, y1) -> tuple[float, float]:
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    return dx / length, dy / length


def _tree(d: ImageDraw.ImageDraw) -> None:
    """The small grey org tree shared by the model and edit glyphs."""
    _elbow(d, 300, 420, 150, 760, _TEXT, 38)
    _elbow(d, 300, 420, 450, 760, _TEXT, 38)
    _circle(d, 300, 360, 105, outline=_TEXT, width=40)
    _circle(d, 150, 840, 82, outline=_TEXT, width=38)
    _circle(d, 450, 840, 82, outline=_TEXT, width=38)


def model_org() -> Image.Image:
    img = _canvas()
    d = ImageDraw.Draw(img)
    _elbow(d, 512, 330, 250, 700, _TEXT, 44)
    _elbow(d, 512, 330, 774, 700, _TEXT, 44)
    _circle(d, 512, 250, 150, fill=_ACCENT)
    _circle(d, 250, 800, 118, outline=_TEXT, width=46)
    _circle(d, 774, 800, 118, outline=_TEXT, width=46)
    return img


def edit_org() -> Image.Image:
    img = _canvas()
    d = ImageDraw.Draw(img)
    _tree(d)
    # Pencil along one axis: amber body, blue inner stripe, red wedge tip
    # whose shoulders sit perpendicular to the body at its end.
    x0, y0, x1, y1 = 870, 170, 660, 590
    ux, uy = _unit(x0, y0, x1, y1)
    px, py = -uy, ux
    half = 60
    d.line(_s(x0, y0, x1, y1), fill=_ACCENT, width=2 * half * _SCALE)
    _circle(d, x0, y0, half, fill=_ACCENT)
    d.line(_s(x0, y0, x1, y1), fill=_BLUE, width=44 * _SCALE)
    _circle(d, x0, y0, 22, fill=_BLUE)
    tip_len = 170
    d.polygon(
        _s(
            x1 + px * half,
            y1 + py * half,
            x1 - px * half,
            y1 - py * half,
            x1 + ux * tip_len,
            y1 + uy * tip_len,
        ),
        fill=_RED,
    )
    return img


def guide() -> Image.Image:
    img = _canvas()
    d = ImageDraw.Draw(img)
    radius = 18
    d.rounded_rectangle(_s(110, 750, 380, 920), radius=radius * _SCALE, fill=_MUTED)
    d.rounded_rectangle(_s(380, 580, 650, 920), radius=radius * _SCALE, fill=_MUTED)
    d.rounded_rectangle(_s(650, 410, 920, 920), radius=radius * _SCALE, fill=_MUTED)
    # One straight climbing shaft with an aligned head at its end.
    x0, y0, x1, y1 = 170, 660, 790, 270
    ux, uy = _unit(x0, y0, x1, y1)
    px, py = -uy, ux
    d.line(_s(x0, y0, x1, y1), fill=_ACCENT, width=76 * _SCALE)
    _circle(d, x0, y0, 38, fill=_ACCENT)
    head_len = 220
    half_width = 130
    tip_x, tip_y = x1 + ux * 110, y1 + uy * 110
    bx, by = tip_x - ux * head_len, tip_y - uy * head_len
    d.polygon(
        _s(
            tip_x,
            tip_y,
            bx + px * half_width,
            by + py * half_width,
            bx - px * half_width,
            by - py * half_width,
        ),
        fill=_ACCENT,
    )
    return img


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    icons = {"model_org": model_org(), "edit_org": edit_org(), "guide": guide()}
    for name, image in icons.items():
        for size in _SIZES:
            path = OUTPUT_DIR / f"{name}_{size}.png"
            image.resize((size, size), Image.LANCZOS).save(path)
            print(f"[icons] wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
