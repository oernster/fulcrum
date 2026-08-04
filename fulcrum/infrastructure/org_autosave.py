"""Autosave of the current session, so a model and its moves survive closing.

The file's top level is the current org as plain JSON (the same shape a
plan's initial_org uses, and exactly what older builds wrote), with two
optional keys beside it: the starting org and the move history, which is
what lets the next launch rebuild the session by replay. Both directions
stay compatible: a pre-history file restores as an org with no moves and an
older build reading a new file still finds the org it expects at the top
level. Writes are atomic; a missing file means nothing to restore and an
unreadable history degrades to the org alone.

A file that is present but will not parse is never left where the next save
can land on it. It is moved aside first, and if even that fails the store
seals itself and writes nothing at all, because the session in memory can be
replayed and the one on disk cannot be brought back.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fulcrum.application.dto import SessionSnapshot
from fulcrum.domain.errors import FulcrumError
from fulcrum.infrastructure.json_serialization import (
    move_from_dict,
    move_to_dict,
    org_from_dict,
    org_to_dict,
)

_APP_DIR = ".fulcrum"
_FILENAME = "last_org.json"
_JSON_INDENT = 2
_TMP_SUFFIX = ".tmp"
_INITIAL_KEY = "initial_org"
_HISTORY_KEY = "history"
# A file that is present but will not read is kept under this suffix rather
# than left in place to be overwritten. The launch that cannot restore starts
# a new session and saves it immediately, so without this the unreadable file
# (which may be a whole organisation and its record) is gone within seconds of
# the failure and nothing anywhere reports it.
_PRESERVED_SUFFIX = ".unreadable"
_PRESERVE_ATTEMPTS = 100


def move_file(source: Path, target: Path) -> bool:
    """Move a file, reporting whether it worked rather than raising.

    The caller's decision depends on the answer rather than on the reason:
    a file that cannot be moved out of the way is a file that must not be
    written over.
    """
    try:
        os.replace(source, target)
    except OSError:
        return False
    return True


def default_autosave_path() -> Path:
    """The per-user location the current session is saved to and restored from."""
    return Path.home() / _APP_DIR / _FILENAME


class FileOrgStore:
    """Implements the application's OrgStore over a single JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path if path is not None else default_autosave_path()
        self._preserved: Path | None = None
        self._sealed = False

    @property
    def preserved_copy(self) -> Path | None:
        """Where an unreadable file was kept, once one has been found."""
        return self._preserved

    @property
    def is_sealed(self) -> bool:
        """True when saving is refused because the old file could not be kept."""
        return self._sealed

    def save(self, snapshot: SessionSnapshot) -> None:
        """Write the session atomically, unless the store has been sealed.

        Sealing is the last line of defence: an existing file that could not
        be read and could not be moved aside is left exactly as it is. Losing
        this session is recoverable by replaying it; overwriting the previous
        one is not.
        """
        if self._sealed:
            return
        data = org_to_dict(snapshot.org)
        if snapshot.moves:
            data[_INITIAL_KEY] = org_to_dict(snapshot.initial_org)
            data[_HISTORY_KEY] = [move_to_dict(move) for move in snapshot.moves]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + _TMP_SUFFIX)
        tmp.write_text(json.dumps(data, indent=_JSON_INDENT), encoding="utf-8")
        os.replace(tmp, self._path)

    def load(self) -> SessionSnapshot | None:
        """Read the saved session, or None when absent or unreadable.

        A file without history (or with history that fails to parse) loads
        as the current org with no moves, matching the pre-history format.
        """
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError:
            self._sealed = True
            return None
        try:
            data = json.loads(text)
            org = org_from_dict(data)
        except (ValueError, KeyError, FulcrumError):
            self._preserve()
            return None
        try:
            moves = tuple(move_from_dict(m) for m in data.get(_HISTORY_KEY, ()))
            initial = org_from_dict(data[_INITIAL_KEY]) if moves else org
        except (ValueError, KeyError, TypeError, FulcrumError):
            return SessionSnapshot(org, (), org)
        return SessionSnapshot(initial, moves, org)

    def _preserve(self) -> None:
        """Move an unreadable file aside, or seal the store when that fails."""
        candidate = self._free_preserved_path()
        if candidate is None or not move_file(self._path, candidate):
            self._sealed = True
            return
        self._preserved = candidate

    def _free_preserved_path(self) -> Path | None:
        """The first unused preserved name, so an earlier rescue is not lost."""
        for attempt in range(_PRESERVE_ATTEMPTS):
            suffix = (
                _PRESERVED_SUFFIX if attempt == 0 else f"{_PRESERVED_SUFFIX}{attempt}"
            )
            candidate = self._path.with_name(self._path.name + suffix)
            if not candidate.exists():
                return candidate
        return None
