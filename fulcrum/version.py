"""Application identity and version.

One place for app identity so the runtime UI, the About dialog and packaging
metadata stay consistent.
"""

from __future__ import annotations

from pathlib import Path

APP_NAME: str = "Fulcrum"
APP_TAGLINE: str = "Decision Sandbox"
APP_AUTHOR: str = "Oliver Ernster"
APP_COPYRIGHT: str = "(c) 2026 Oliver Ernster"

# Windows taskbar grouping / pinned-icon identity. Keep this stable over time;
# changing it makes Windows treat newer builds as a separate app.
APP_APPUSERMODELID: str = "uk.codecrafter.fulcrum"

# Single source of truth for the version: the VERSION file in the repo root.
_VERSION_FILE = Path(__file__).resolve().parents[1] / "VERSION"
_FALLBACK_VERSION = "0.0.0-dev"
__version__: str = (
    _VERSION_FILE.read_text(encoding="utf-8").strip()
    if _VERSION_FILE.exists()
    else _FALLBACK_VERSION
)
