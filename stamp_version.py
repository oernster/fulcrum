#!/usr/bin/env python3
"""Stamp the single-source version into static documentation files.

The repository keeps exactly one real version string: the VERSION file in the
project root. Python code reads it at runtime (fulcrum.version, the dynamic
pyproject metadata and the build scripts). Static files cannot read VERSION at
render time, so they instead carry a delimited token:

    <!--VERSION-->0.2.0<!--/VERSION-->

This script reads VERSION and rewrites whatever sits between every such token's
delimiters, across the root Markdown and the GitHub Pages site under docs/. It
is idempotent: stamping an already-current file changes nothing. Static files
are stamped from VERSION, never hand-edited, so a version cannot drift.

Usage (from the project root):

    python stamp_version.py

Run it on every version bump and before each packaging build, so a release
always ships documentation whose version matches VERSION.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VERSION_FILE = PROJECT_ROOT / "VERSION"
DOCS_DIR = PROJECT_ROOT / "docs"
DEFAULT_VERSION = "0.0.0-dev"

# Delimiters that bracket a stamped version in any static file. The text
# between them is owned by this script and overwritten from VERSION each run.
VERSION_TOKEN_OPEN = "<!--VERSION-->"
VERSION_TOKEN_CLOSE = "<!--/VERSION-->"
VERSION_TOKEN_PATTERN = re.compile(
    re.escape(VERSION_TOKEN_OPEN) + ".*?" + re.escape(VERSION_TOKEN_CLOSE),
    re.DOTALL,
)


def read_version() -> str:
    """Return the project version from the VERSION file, or a safe default."""
    try:
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        version = ""
    return version or DEFAULT_VERSION


def target_files() -> list[Path]:
    """Return the static files that may carry a version token, deduplicated.

    The surface is the root-level Markdown plus the GitHub Pages site under
    docs/ (its HTML and any Markdown).
    """
    candidates: set[Path] = set(PROJECT_ROOT.glob("*.md"))
    if DOCS_DIR.is_dir():
        candidates.update(DOCS_DIR.rglob("*.html"))
        candidates.update(DOCS_DIR.rglob("*.md"))
    return sorted(candidates)


def stamp_file(path: Path, version: str) -> bool:
    """Rewrite version tokens in one file. Return True if the file changed."""
    original = path.read_bytes().decode("utf-8")
    stamped = VERSION_TOKEN_PATTERN.sub(
        lambda _match: f"{VERSION_TOKEN_OPEN}{version}{VERSION_TOKEN_CLOSE}",
        original,
    )
    if stamped == original:
        return False
    path.write_bytes(stamped.encode("utf-8"))
    return True


def main() -> int:
    version = read_version()
    changed = [path for path in target_files() if stamp_file(path, version)]
    print(f"[stamp_version] VERSION = {version}")
    if not changed:
        print("[stamp_version] No files needed stamping.")
        return 0
    for path in changed:
        print(f"[stamp_version] Stamped {path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
