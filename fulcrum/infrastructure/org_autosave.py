"""Autosave of the current org, so a model survives closing the app.

The current org is written as plain JSON (the same shape a plan's initial_org
uses) to a fixed per-user path. On the next launch the app restores it instead
of generating a fresh random org, which is what lets "Edit my org" reopen the
structure the user built in an earlier session. Writes are atomic; a missing or
unreadable file simply means there is nothing to restore.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fulcrum.domain.errors import FulcrumError
from fulcrum.domain.models import OrgState
from fulcrum.infrastructure.json_serialization import org_from_dict, org_to_dict

_APP_DIR = ".fulcrum"
_FILENAME = "last_org.json"
_JSON_INDENT = 2
_TMP_SUFFIX = ".tmp"


def default_autosave_path() -> Path:
    """The per-user location the current org is saved to and restored from."""
    return Path.home() / _APP_DIR / _FILENAME


class FileOrgStore:
    """Implements the application's OrgStore over a single JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path if path is not None else default_autosave_path()

    def save(self, org: OrgState) -> None:
        """Write the org atomically to the autosave path."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + _TMP_SUFFIX)
        tmp.write_text(
            json.dumps(org_to_dict(org), indent=_JSON_INDENT), encoding="utf-8"
        )
        os.replace(tmp, self._path)

    def load(self) -> OrgState | None:
        """Read the saved org, or None when absent or unreadable."""
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return org_from_dict(data)
        except (OSError, ValueError, KeyError, FulcrumError):
            return None
