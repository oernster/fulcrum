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


def main() -> int:
    root = Path(__file__).resolve().parent
    source = electric_glow(Image.open(root / _SOURCE))
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
