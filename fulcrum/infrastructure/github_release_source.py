"""GitHub releases adapter for the update check.

``releases/latest`` returns only a published, non-draft, non-prerelease
release, so a tag pushed mid-development is structurally invisible; the guard
is the endpoint's own contract. One check at launch plus one per day sits far
inside the unauthenticated rate limit, so there are no retries. Every failure
mode collapses to None.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable

from fulcrum.application.update_info import ReleaseAsset, ReleaseInfo

_API_URL = "https://api.github.com/repos/oernster/fulcrum/releases/latest"
_ACCEPT_HEADER = "application/vnd.github+json"
_TIMEOUT_SECONDS = 5.0

# urllib.request.urlopen's shape; tests inject a fake so nothing here ever
# touches the network.
Opener = Callable[..., Any]


def _parse_assets(raw: object) -> tuple[ReleaseAsset, ...]:
    """The well-formed assets from the payload, dropping the rest."""
    if not isinstance(raw, list):
        return ()
    assets: list[ReleaseAsset] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        download_url = entry.get("browser_download_url")
        if isinstance(name, str) and name and isinstance(download_url, str):
            assets.append(ReleaseAsset(name=name, download_url=download_url))
    return tuple(assets)


class GitHubReleaseSource:
    """Implements the application's ReleaseSource over the GitHub API."""

    def __init__(self, opener: Opener | None = None) -> None:
        self._opener: Opener = opener or urllib.request.urlopen

    def latest_release(self) -> ReleaseInfo | None:
        request = urllib.request.Request(_API_URL, headers={"Accept": _ACCEPT_HEADER})
        try:
            with self._opener(request, timeout=_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        tag = payload.get("tag_name")
        if not isinstance(tag, str) or not tag.strip():
            return None
        page_url = payload.get("html_url")
        return ReleaseInfo(
            version=tag.strip(),
            page_url=page_url if isinstance(page_url, str) and page_url else None,
            assets=_parse_assets(payload.get("assets")),
        )
