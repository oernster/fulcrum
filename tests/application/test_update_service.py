"""The update check's offer decision: version compare, skip and asset pick."""

import pytest

from fulcrum.application.update_info import ReleaseAsset, ReleaseInfo
from fulcrum.application.update_service import (
    UpdateService,
    is_newer,
    platform_key_for,
    select_asset_url,
)

ASSETS = (
    ReleaseAsset("FulcrumSetup.exe", "https://example.com/FulcrumSetup.exe"),
    ReleaseAsset("fulcrum.dmg", "https://example.com/fulcrum.dmg"),
    ReleaseAsset("fulcrum.flatpak", "https://example.com/fulcrum.flatpak"),
)


class FakeReleaseSource:
    def __init__(self, release=None):
        self._release = release

    def latest_release(self):
        return self._release


def release(version="v4.4.0", assets=ASSETS):
    return ReleaseInfo(
        version=version,
        page_url="https://github.com/oernster/fulcrum/releases/latest",
        assets=assets,
    )


class TestIsNewer:
    def test_newer(self):
        assert is_newer("4.4.0", "4.3.0") is True

    def test_equal(self):
        assert is_newer("4.3.0", "4.3.0") is False

    def test_older(self):
        assert is_newer("4.2.9", "4.3.0") is False

    def test_v_prefix_stripped(self):
        assert is_newer("v4.4.0", "4.3.0") is True

    def test_uppercase_v_prefix_stripped(self):
        assert is_newer("V4.4.0", "4.3.0") is True

    def test_whitespace_tolerated(self):
        assert is_newer("  4.4.0  ", "4.3.0") is True

    def test_extra_component_compares_positionally(self):
        assert is_newer("4.4", "4.3.0") is True
        assert is_newer("4.3.0.1", "4.3.0") is True

    @pytest.mark.parametrize("latest", ["", "not-a-version", "4.4.0-rc1", "4..0"])
    def test_malformed_latest_is_not_newer(self, latest):
        assert is_newer(latest, "4.3.0") is False

    @pytest.mark.parametrize("current", ["", "0.0.0-dev", "garbage"])
    def test_malformed_current_is_not_newer(self, current):
        assert is_newer("4.4.0", current) is False


class TestCheck:
    def test_unreachable_source_returns_none(self):
        service = UpdateService(FakeReleaseSource(None), "4.3.0", "windows")
        assert service.check() is None

    def test_newer_release_offers_update_with_asset_and_page(self):
        service = UpdateService(FakeReleaseSource(release()), "4.3.0", "windows")
        status = service.check()
        assert status.update_available is True
        assert status.latest == "v4.4.0"
        assert status.current == "4.3.0"
        assert status.download_url == "https://example.com/FulcrumSetup.exe"
        assert status.page_url is not None

    def test_same_version_is_not_offered(self):
        service = UpdateService(
            FakeReleaseSource(release("v4.3.0")), "4.3.0", "windows"
        )
        status = service.check()
        assert status.update_available is False
        assert status.download_url is None

    def test_skipped_version_is_seen_but_not_offered(self):
        service = UpdateService(FakeReleaseSource(release()), "4.3.0", "windows")
        status = service.check(skipped_version="v4.4.0")
        assert status.update_available is False
        assert status.latest == "v4.4.0"
        assert status.download_url is None

    def test_different_skipped_version_still_offers(self):
        service = UpdateService(FakeReleaseSource(release()), "4.3.0", "windows")
        assert service.check(skipped_version="v4.3.9").update_available is True

    @pytest.mark.parametrize(
        "platform_key,expected",
        [
            ("windows", "https://example.com/FulcrumSetup.exe"),
            ("macos", "https://example.com/fulcrum.dmg"),
            ("linux", "https://example.com/fulcrum.flatpak"),
        ],
    )
    def test_platform_asset_selection(self, platform_key, expected):
        service = UpdateService(FakeReleaseSource(release()), "4.3.0", platform_key)
        assert service.check().download_url == expected

    def test_no_matching_asset_falls_back_to_page_only(self):
        source = FakeReleaseSource(
            release(assets=(ReleaseAsset("checksums.txt", "https://x/c"),))
        )
        service = UpdateService(source, "4.3.0", "windows")
        status = service.check()
        assert status.update_available is True
        assert status.download_url is None


class TestSelectAssetUrl:
    def test_suffix_match_is_case_insensitive(self):
        assets = (ReleaseAsset("FULCRUMSETUP.EXE", "https://x/setup"),)
        assert select_asset_url(assets, "windows") == "https://x/setup"

    def test_empty_assets(self):
        assert select_asset_url((), "windows") is None

    def test_unknown_platform_key(self):
        assert select_asset_url(ASSETS, "beos") is None


class TestPlatformKeyFor:
    @pytest.mark.parametrize(
        "sys_platform,expected",
        [
            ("win32", "windows"),
            ("darwin", "macos"),
            ("linux", "linux"),
            ("freebsd14", "linux"),
        ],
    )
    def test_mapping(self, sys_platform, expected):
        assert platform_key_for(sys_platform) == expected
