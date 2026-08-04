"""Reads of the installer's own payload: version, licences and icon.

This is the one place the installer asks where it is. Under the onefile
build that answer is the bootstrap's unpacked directory, which is where
Nuitka places the embedded payload and the licence files, so every other
module takes the bundle root from here rather than reading ``__file__``
for itself.

British spelling is used in comments. No em dashes appear anywhere.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

import installer_logic as logic


def bundle_root() -> Path:
    """Return the directory holding the unpacked payload and licences."""
    return Path(__file__).resolve().parent


def licence_text(file_name: str) -> str:
    """Return a bundled licence text by file name, or a fallback if absent."""
    return logic.first_readable_text(
        logic.licence_candidates(file_name, bundle_root()),
        logic.LICENSE_FALLBACK,
    )


def installer_licence_text() -> str:
    """Return the installer-wrapper licence notice, or a fallback if absent."""
    return logic.first_readable_text(
        logic.licence_candidates(logic.INSTALLER_LICENSE_FILE_NAME, bundle_root()),
        logic.INSTALLER_LICENSE_FALLBACK,
    )


def app_version() -> str:
    """Return the bundled application version, or an empty string if absent."""
    return logic.first_version(logic.version_candidates(bundle_root()))


def app_icon() -> QIcon:
    """Return the bundled application icon, or an empty icon when absent."""
    path = logic.payload_app_dir(bundle_root()) / logic.ICON_FILE_NAME
    if path.is_file():
        return QIcon(str(path))
    return QIcon()
