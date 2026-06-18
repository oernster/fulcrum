"""Runtime discovery of bundled assets (icon, licence). No Qt dependency.

Looks beside the executable (frozen builds), in the PyInstaller temp dir, in the
repo root (dev mode) and finally the working directory, so the same code finds
assets whether running from source or from an installed build.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ICON_FILENAMES = (
    "fulcrum.ico",
    "fulcrum_256.png",
    "fulcrum_128.png",
    "fulcrum_64.png",
    "fulcrum_48.png",
    "fulcrum_32.png",
    "fulcrum.png",
)
_PNG_SUFFIX = ".png"
_LICENSE_FILENAME = "LICENSE"
_BOOK_COVER_SUBDIR = ("assets", "books")


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    try:
        roots.append(Path(sys.executable).resolve().parent)
    except OSError:
        pass
    roots.append(Path(__file__).resolve().parents[2])
    roots.append(Path.cwd())
    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def find_app_icon() -> Path | None:
    """Best icon for the window and taskbar, preferring a native .ico."""
    for root in _candidate_roots():
        for name in _ICON_FILENAMES:
            candidate = root / name
            if candidate.is_file():
                return candidate
    return None


def find_about_png() -> Path | None:
    """A PNG icon for the About dialog (reliably loadable by Qt everywhere)."""
    for root in _candidate_roots():
        for name in _ICON_FILENAMES:
            if name.endswith(_PNG_SUFFIX):
                candidate = root / name
                if candidate.is_file():
                    return candidate
    return None


def find_license() -> Path | None:
    """Locate the bundled LICENSE file for the Licence dialog."""
    for root in _candidate_roots():
        candidate = root / _LICENSE_FILENAME
        if candidate.is_file():
            return candidate
    return None


def find_book_cover(filename: str) -> Path | None:
    """Locate a bundled book-cover PNG by filename (dev tree or frozen build)."""
    for root in _candidate_roots():
        candidate = root.joinpath(*_BOOK_COVER_SUBDIR, filename)
        if candidate.is_file():
            return candidate
    return None


def find_data_file(filename: str) -> Path | None:
    """Locate a bundled top-level data file (e.g. a stepper arrow) by name."""
    for root in _candidate_roots():
        candidate = root / filename
        if candidate.is_file():
            return candidate
    return None
