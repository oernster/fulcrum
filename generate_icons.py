"""Generate multi-size PNG and ICO icons for Fulcrum from fulcrum.png.

Run from the repo root: python generate_icons.py. The window and taskbar use
the ICO; the About dialog and the header's overview button use
fulcrum_256.png; the installer, DMG and Flatpak bundle the same set.

The master artwork is dark-on-black; every emitted icon gets the approved
"electric glow" treatment first: the near-black backdrop is keyed to full
transparency (alpha follows luminance, so the glow keeps its soft edges),
the colours are lifted to read on dark surfaces and a thinned blur of the
art is composited beneath it as a halo. Deterministic: same master, same
icons.
"""

from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

_SOURCE = "fulcrum.png"
_PNG_SIZES = (16, 32, 48, 64, 128, 256, 512, 1024)
_ICO_SIZES = (16, 32, 48, 64, 128, 256)
_PNG_TEMPLATE = "fulcrum_{size}.png"
_ICO_NAME = "fulcrum.ico"
_RESAMPLE = Image.Resampling.LANCZOS

# The electric-glow treatment: background floor cut, alpha gain, colour and
# saturation lift, halo blur radius and the divisor thinning the halo.
_KEY_FLOOR = 14
_KEY_GAIN = 4.0
_SATURATION = 1.5
_BRIGHTNESS = 2.6
_HALO_BLUR = 16
_HALO_THIN = 2

# The provenance sibling: the same mark retinted golden (the approved
# "golden" candidate: hue set uniformly, saturation eased) then given the
# same glow, so the header's numbers button reads as the app icon's kin.
_PROVENANCE_NAME = "fulcrum_provenance_256.png"
_PROVENANCE_SIZE = 256
_PROVENANCE_HUE_DEG = 38
_PROVENANCE_SAT = 0.85
_HUE_MAX = 360
_CHANNEL_MAX = 255

# The master carries wide margins that read as padding in the taskbar and
# title bar, and its raw alpha bounds are held open by sparse streak tails,
# so the trim keys on alpha MASS instead: crop to the box holding this share
# of the ink, pad by the margin, then square. The letterbox cap bounds how
# much taller than the ink the square may go; the wide axis centre-crops to
# meet it, which only sheds the dim trail tips beyond the mass box.
_TRIM_KEEP = 0.995
_TRIM_MARGIN_RATIO = 0.03
_MAX_LETTERBOX = 1.15


def retint(master: Image.Image, hue_deg: int, sat_scale: float) -> Image.Image:
    """The master with every pixel's hue set and saturation scaled."""
    h, s, v = master.convert("RGB").convert("HSV").split()
    hue = int(hue_deg / _HUE_MAX * _CHANNEL_MAX)
    h = h.point(lambda _: hue)
    s = s.point(lambda x: min(_CHANNEL_MAX, int(x * sat_scale)))
    return Image.merge("HSV", (h, s, v)).convert("RGB")


def electric_glow(master: Image.Image) -> Image.Image:
    """The approved icon treatment: keyed, lifted, haloed."""
    rgb = master.convert("RGB")
    lum = rgb.convert("L")
    alpha = lum.point(
        lambda v: 0 if v < _KEY_FLOOR else min(255, int((v - _KEY_FLOOR) * _KEY_GAIN))
    )
    art = ImageEnhance.Color(rgb).enhance(_SATURATION)
    art = ImageEnhance.Brightness(art).enhance(_BRIGHTNESS)
    base = art.copy()
    base.putalpha(alpha)
    glow = base.filter(ImageFilter.GaussianBlur(_HALO_BLUR))
    r, g, b, a = glow.split()
    glow = Image.merge("RGBA", (r, g, b, a.point(lambda v: v // _HALO_THIN)))
    out = Image.new("RGBA", base.size, (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(base)
    return out


def _mass_span(sums: list[int], keep: float) -> tuple[int, int]:
    """The index range holding the central `keep` share of the mass."""
    total = sum(sums)
    lo_target = total * (1 - keep) / 2
    hi_target = total * (1 + keep) / 2
    running = 0.0
    lo = 0
    hi = len(sums)
    for index, value in enumerate(sums):
        running += value
        if running < lo_target:
            lo = index + 1
        if running < hi_target:
            hi = index + 1
    return lo, min(hi + 1, len(sums))


def tighten(art: Image.Image) -> Image.Image:
    """Crop to the ink's mass box, then square within the letterbox cap."""
    alpha = art.getchannel("A")
    width, height = alpha.size
    data = alpha.tobytes()
    cols = [0] * width
    rows = [0] * height
    for y in range(height):
        base = y * width
        row_total = 0
        for x in range(width):
            value = data[base + x]
            cols[x] += value
            row_total += value
        rows[y] = row_total
    x0, x1 = _mass_span(cols, _TRIM_KEEP)
    y0, y1 = _mass_span(rows, _TRIM_KEEP)
    if x1 <= x0 or y1 <= y0:
        return art
    margin = round(max(x1 - x0, y1 - y0) * _TRIM_MARGIN_RATIO)
    cropped = art.crop(
        (
            max(0, x0 - margin),
            max(0, y0 - margin),
            min(width, x1 + margin),
            min(height, y1 + margin),
        )
    )
    side = min(max(cropped.size), round(min(cropped.size) * _MAX_LETTERBOX))
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2))
    return out


def main() -> int:
    root = Path(__file__).resolve().parent
    source = tighten(electric_glow(Image.open(root / _SOURCE)))
    for size in _PNG_SIZES:
        name = _PNG_TEMPLATE.format(size=size)
        source.resize((size, size), _RESAMPLE).save(root / name, "PNG")
        print(f"  [OK] {name}")
    ico_base = source.resize((max(_ICO_SIZES), max(_ICO_SIZES)), _RESAMPLE)
    ico_base.save(
        root / _ICO_NAME,
        format="ICO",
        sizes=[(size, size) for size in _ICO_SIZES],
    )
    print(f"  [OK] {_ICO_NAME}")
    provenance = tighten(
        electric_glow(
            retint(Image.open(root / _SOURCE), _PROVENANCE_HUE_DEG, _PROVENANCE_SAT)
        )
    )
    provenance.resize((_PROVENANCE_SIZE, _PROVENANCE_SIZE), _RESAMPLE).save(
        root / _PROVENANCE_NAME, "PNG"
    )
    print(f"  [OK] {_PROVENANCE_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
