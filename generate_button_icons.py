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

# One palette per theme: the dark-theme glyphs use light strokes, the
# light-theme variants (emitted with a _light suffix) use dark strokes with
# the amber deepened so it reads as ink on a light surface.
_DARK = {
    "text": "#e6e9ee",
    "muted": "#9aa3af",
    "accent": "#f59e0b",
    "blue": "#60a5fa",
    "red": "#ef4444",
}
_LIGHT = {
    "text": "#3b4350",
    "muted": "#8a94a4",
    "accent": "#d97706",
    "blue": "#2563eb",
    "red": "#dc2626",
}
_VARIANTS = (("", _DARK), ("_light", _LIGHT))


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


def _tree(d: ImageDraw.ImageDraw, p: dict) -> None:
    """The small grey org tree shared by the model and edit glyphs."""
    _elbow(d, 300, 420, 150, 760, p["text"], 38)
    _elbow(d, 300, 420, 450, 760, p["text"], 38)
    _circle(d, 300, 360, 105, outline=p["text"], width=40)
    _circle(d, 150, 840, 82, outline=p["text"], width=38)
    _circle(d, 450, 840, 82, outline=p["text"], width=38)


def model_org(p: dict) -> Image.Image:
    img = _canvas()
    d = ImageDraw.Draw(img)
    _elbow(d, 512, 330, 250, 700, p["text"], 44)
    _elbow(d, 512, 330, 774, 700, p["text"], 44)
    _circle(d, 512, 250, 150, fill=p["accent"])
    _circle(d, 250, 800, 118, outline=p["text"], width=46)
    _circle(d, 774, 800, 118, outline=p["text"], width=46)
    return img


def edit_org(p: dict) -> Image.Image:
    img = _canvas()
    d = ImageDraw.Draw(img)
    _tree(d, p)
    # Pencil along one axis: amber body, blue inner stripe, red wedge tip
    # whose shoulders sit perpendicular to the body at its end.
    x0, y0, x1, y1 = 870, 170, 660, 590
    ux, uy = _unit(x0, y0, x1, y1)
    px, py = -uy, ux
    half = 60
    d.line(_s(x0, y0, x1, y1), fill=p["accent"], width=2 * half * _SCALE)
    _circle(d, x0, y0, half, fill=p["accent"])
    d.line(_s(x0, y0, x1, y1), fill=p["blue"], width=44 * _SCALE)
    _circle(d, x0, y0, 22, fill=p["blue"])
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
        fill=p["red"],
    )
    return img


def guide(p: dict) -> Image.Image:
    img = _canvas()
    d = ImageDraw.Draw(img)
    radius = 18
    d.rounded_rectangle(_s(110, 750, 380, 920), radius=radius * _SCALE, fill=p["muted"])
    d.rounded_rectangle(_s(380, 580, 650, 920), radius=radius * _SCALE, fill=p["muted"])
    d.rounded_rectangle(_s(650, 410, 920, 920), radius=radius * _SCALE, fill=p["muted"])
    # One straight climbing shaft with an aligned head at its end.
    x0, y0, x1, y1 = 170, 660, 790, 270
    ux, uy = _unit(x0, y0, x1, y1)
    px, py = -uy, ux
    d.line(_s(x0, y0, x1, y1), fill=p["accent"], width=76 * _SCALE)
    _circle(d, x0, y0, 38, fill=p["accent"])
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
        fill=p["accent"],
    )
    return img


def view_complete(p: dict) -> Image.Image:
    """The complete-picture view: every node visible inside one frame."""
    img = _canvas()
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        _s(140, 140, 884, 884), radius=60 * _SCALE, outline=p["text"], width=40 * _SCALE
    )
    for cx in (300, 512, 724):
        for cy in (300, 512, 724):
            colour = p["accent"] if (cx, cy) == (512, 512) else p["muted"]
            _circle(d, cx, cy, 55, fill=colour)
    return img


def view_drill(p: dict) -> Image.Image:
    """The drill-down view: an arrow diving into a nested frame."""
    img = _canvas()
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        _s(140, 140, 884, 884), radius=60 * _SCALE, outline=p["text"], width=40 * _SCALE
    )
    d.rounded_rectangle(_s(470, 470, 810, 810), radius=40 * _SCALE, fill=p["muted"])
    x0, y0, x1, y1 = 260, 260, 580, 580
    ux, uy = _unit(x0, y0, x1, y1)
    px, py = -uy, ux
    d.line(_s(x0, y0, x1, y1), fill=p["accent"], width=70 * _SCALE)
    _circle(d, x0, y0, 35, fill=p["accent"])
    head_len = 180
    half_width = 110
    tip_x, tip_y = x1 + ux * 100, y1 + uy * 100
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
        fill=p["accent"],
    )
    return img


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for suffix, palette in _VARIANTS:
        icons = {
            "model_org": model_org(palette),
            "edit_org": edit_org(palette),
            "guide": guide(palette),
            "view_complete": view_complete(palette),
            "view_drill": view_drill(palette),
        }
        for name, image in icons.items():
            for size in _SIZES:
                path = OUTPUT_DIR / f"{name}{suffix}_{size}.png"
                image.resize((size, size), Image.LANCZOS).save(path)
                print(f"[icons] wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
