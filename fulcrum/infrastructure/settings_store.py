"""Persistence for small user preferences, currently the theme choice.

A single JSON file beside the session autosave. Writes are atomic; a
missing or unreadable file (or an unknown theme name) degrades to the
default theme, so preferences can never stop the app from starting.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_APP_DIR = ".fulcrum"
_FILENAME = "settings.json"
_JSON_INDENT = 2
_TMP_SUFFIX = ".tmp"
_THEME_KEY = "theme"
_KNOWN_THEMES = ("dark", "light")
_DEFAULT_THEME = "dark"
_SKIPPED_UPDATE_KEY = "skipped_update_version"


def default_settings_path() -> Path:
    """The per-user location preferences are saved to and restored from."""
    return Path.home() / _APP_DIR / _FILENAME


class FileSettingsStore:
    """Implements the application's SettingsStore over a single JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path if path is not None else default_settings_path()

    def load_theme(self) -> str:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return _DEFAULT_THEME
        theme = data.get(_THEME_KEY) if isinstance(data, dict) else None
        return theme if theme in _KNOWN_THEMES else _DEFAULT_THEME

    def save_theme(self, theme: str) -> None:
        data = self._read_all()
        data[_THEME_KEY] = theme
        self._write_all(data)

    def load_skipped_update_version(self) -> str | None:
        """The exact release tag the user chose to skip, else None."""
        value = self._read_all().get(_SKIPPED_UPDATE_KEY)
        return value if isinstance(value, str) and value else None

    def save_skipped_update_version(self, version: str) -> None:
        data = self._read_all()
        data[_SKIPPED_UPDATE_KEY] = version
        self._write_all(data)

    def _write_all(self, data: dict) -> None:
        """Atomically replace the settings file with ``data``."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + _TMP_SUFFIX)
        tmp.write_text(json.dumps(data, indent=_JSON_INDENT), encoding="utf-8")
        os.replace(tmp, self._path)

    def _read_all(self) -> dict:
        """The whole settings dict, kept so future keys survive a theme save."""
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}
