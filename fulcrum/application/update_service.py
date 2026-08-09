"""The update check's offer decision.

Version strings compare as dotted integer tuples with an optional leading
``v``. Anything unparseable compares as not-newer, so a malformed tag can
never raise a spurious prompt and a ``0.0.0-dev`` source run stays silent.
"""

from __future__ import annotations

from fulcrum.application.interfaces import ReleaseSource
from fulcrum.application.update_info import ReleaseAsset, UpdateStatus

_PLATFORM_SUFFIXES = {
    "windows": ".exe",
    "macos": ".dmg",
    "linux": ".flatpak",
}

_SYS_PLATFORM_KEYS = {
    "win32": "windows",
    "darwin": "macos",
}

_DEFAULT_PLATFORM_KEY = "linux"


def _parse(version: str) -> tuple[int, ...] | None:
    text = version.strip()
    if text[:1] in ("v", "V"):
        text = text[1:]
    try:
        return tuple(int(part) for part in text.split("."))
    except ValueError:
        return None


def is_newer(latest: str, current: str) -> bool:
    """True when ``latest`` is a strictly newer version than ``current``."""
    latest_parts = _parse(latest)
    current_parts = _parse(current)
    if latest_parts is None or current_parts is None:
        return False
    return latest_parts > current_parts


def platform_key_for(sys_platform: str) -> str:
    """Map a ``sys.platform`` value to the asset-selection key."""
    return _SYS_PLATFORM_KEYS.get(sys_platform, _DEFAULT_PLATFORM_KEY)


def select_asset_url(assets: tuple[ReleaseAsset, ...], platform_key: str) -> str | None:
    """First asset whose name matches the platform's suffix, else None."""
    suffix = _PLATFORM_SUFFIXES.get(platform_key)
    if suffix is None:
        return None
    for asset in assets:
        if asset.name.lower().endswith(suffix):
            return asset.download_url
    return None


class UpdateService:
    """Decides whether an update should be offered, and with which download."""

    def __init__(
        self,
        source: ReleaseSource,
        current_version: str,
        platform_key: str,
    ) -> None:
        self._source = source
        self._current_version = current_version
        self._platform_key = platform_key

    def check(self, skipped_version: str | None = None) -> UpdateStatus | None:
        """One update check. None when the release source is unreachable.

        ``skipped_version`` is the exact tag the user chose to skip; both
        sides come from the same endpoint, so string equality is enough. The
        manual check passes None here, which is how it ignores the skip.
        """
        release = self._source.latest_release()
        if release is None:
            return None
        newer = is_newer(release.version, self._current_version)
        available = newer and release.version != skipped_version
        download_url = (
            select_asset_url(release.assets, self._platform_key) if available else None
        )
        return UpdateStatus(
            current=self._current_version,
            latest=release.version,
            update_available=available,
            download_url=download_url,
            page_url=release.page_url,
        )
