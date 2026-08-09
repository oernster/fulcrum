"""DTOs for the in-app update check."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    """One downloadable file attached to a release."""

    name: str
    download_url: str


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    """A published release: its tag, its page and its downloadable assets."""

    version: str
    page_url: str | None
    assets: tuple[ReleaseAsset, ...]


@dataclass(frozen=True, slots=True)
class UpdateStatus:
    """What one check found and what, if anything, to offer."""

    current: str
    latest: str
    update_available: bool
    download_url: str | None
    page_url: str | None
