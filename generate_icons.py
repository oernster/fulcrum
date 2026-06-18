"""Generate multi-size PNG and ICO icons for Fulcrum from fulcrum.png.

Run from the repo root: python generate_icons.py. The window and taskbar use the
ICO; the About dialog uses fulcrum_256.png; the installer bundles both.
"""

from pathlib import Path

from PIL import Image

_SOURCE = "fulcrum.png"
_PNG_SIZES = (16, 32, 48, 64, 128, 256, 512)
_ICO_SIZES = (16, 32, 48, 64, 128, 256)
_PNG_TEMPLATE = "fulcrum_{size}.png"
_ICO_NAME = "fulcrum.ico"
_RESAMPLE = Image.Resampling.LANCZOS


def main() -> int:
    root = Path(__file__).resolve().parent
    source = Image.open(root / _SOURCE).convert("RGBA")
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
