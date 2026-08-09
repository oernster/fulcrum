"""The GitHub releases adapter, driven through an injected fake opener."""

import json

import pytest

from fulcrum.infrastructure.github_release_source import (
    _ACCEPT_HEADER,
    _API_URL,
    _TIMEOUT_SECONDS,
    GitHubReleaseSource,
)

PAYLOAD = {
    "tag_name": "v4.4.0",
    "html_url": "https://github.com/oernster/fulcrum/releases/tag/v4.4.0",
    "assets": [
        {
            "name": "FulcrumSetup.exe",
            "browser_download_url": "https://example.com/FulcrumSetup.exe",
        },
    ],
}


class FakeResponse:
    """Context-manager response with a read(), like urlopen's."""

    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    """Records the request and returns a canned response, or raises."""

    def __init__(self, body=None, error=None):
        self._body = body
        self._error = error
        self.request = None
        self.timeout = None

    def __call__(self, request, timeout=None):
        self.request = request
        self.timeout = timeout
        if self._error is not None:
            raise self._error
        return FakeResponse(self._body)


def source_for(payload):
    return GitHubReleaseSource(FakeOpener(json.dumps(payload).encode("utf-8")))


def test_happy_path():
    release = source_for(PAYLOAD).latest_release()
    assert release.version == "v4.4.0"
    assert release.page_url == PAYLOAD["html_url"]
    assert release.assets[0].name == "FulcrumSetup.exe"


def test_request_target_headers_and_timeout():
    opener = FakeOpener(json.dumps(PAYLOAD).encode("utf-8"))
    GitHubReleaseSource(opener).latest_release()
    assert opener.request.full_url == _API_URL
    assert opener.request.get_header("Accept") == _ACCEPT_HEADER
    assert opener.timeout == _TIMEOUT_SECONDS


def test_network_error_returns_none():
    opener = FakeOpener(error=OSError("unreachable"))
    assert GitHubReleaseSource(opener).latest_release() is None


def test_unparseable_body_returns_none():
    assert GitHubReleaseSource(FakeOpener(b"not json")).latest_release() is None


def test_non_dict_body_returns_none():
    assert GitHubReleaseSource(FakeOpener(b"[1]")).latest_release() is None


@pytest.mark.parametrize("tag", [None, "", "   ", 42])
def test_missing_or_invalid_tag_returns_none(tag):
    payload = dict(PAYLOAD)
    if tag is None:
        del payload["tag_name"]
    else:
        payload["tag_name"] = tag
    assert source_for(payload).latest_release() is None


@pytest.mark.parametrize("page_url", [None, "", 42])
def test_missing_or_invalid_page_url_becomes_none(page_url):
    payload = dict(PAYLOAD)
    if page_url is None:
        del payload["html_url"]
    else:
        payload["html_url"] = page_url
    release = source_for(payload).latest_release()
    assert release is not None
    assert release.page_url is None


@pytest.mark.parametrize("assets", [None, "nope", 42])
def test_missing_or_non_list_assets_become_empty(assets):
    payload = dict(PAYLOAD)
    if assets is None:
        del payload["assets"]
    else:
        payload["assets"] = assets
    release = source_for(payload).latest_release()
    assert release is not None
    assert release.assets == ()


def test_malformed_asset_entries_are_filtered():
    payload = dict(PAYLOAD)
    payload["assets"] = [
        "not-a-dict",
        {"browser_download_url": "https://x/no-name"},
        {"name": "", "browser_download_url": "https://x/empty-name"},
        {"name": "no-url.exe"},
        {"name": 42, "browser_download_url": "https://x/int-name"},
        {"name": "good.exe", "browser_download_url": "https://x/good"},
    ]
    release = source_for(payload).latest_release()
    assert len(release.assets) == 1
    assert release.assets[0].download_url == "https://x/good"


def test_default_opener_is_urlopen():
    import urllib.request

    assert GitHubReleaseSource()._opener is urllib.request.urlopen
