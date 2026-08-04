"""Tests for the installer's payload, licence, version and path decisions.

The installer is a second application shipped inside the first, so its
decisions are gated exactly like the app's application layer: everything
here is pure, and the Windows side effects that carry the decisions out
(installer_ops.py) stay outside the gate with the Qt surface.
"""

import pytest

import installer_logic as logic


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ------------------------------------------------------------------- payload


def test_payload_paths_hang_off_the_bundle_root(tmp_path):
    assert logic.payload_app_dir(tmp_path) == (
        tmp_path / logic.PAYLOAD_DIR_NAME / logic.APP_NAME
    )
    assert logic.payload_archive(tmp_path) == (
        tmp_path / logic.PAYLOAD_DIR_NAME / logic.PAYLOAD_ARCHIVE_NAME
    )


def test_licence_candidates_prefer_the_copy_beside_the_binary(tmp_path):
    candidates = logic.licence_candidates("LICENCE.txt", tmp_path)
    assert candidates == (
        tmp_path / "LICENCE.txt",
        tmp_path / logic.PAYLOAD_DIR_NAME / "LICENCE.txt",
    )


def test_first_readable_text_returns_the_nearest_copy(tmp_path):
    nearest = _write(tmp_path / "LICENCE.txt", "near")
    further = _write(tmp_path / "payload" / "LICENCE.txt", "far")
    assert logic.first_readable_text((nearest, further), "fallback") == "near"
    assert logic.first_readable_text((tmp_path / "gone", further), "x") == "far"


def test_first_readable_text_falls_back_when_nothing_reads(tmp_path):
    missing = (tmp_path / "one", tmp_path / "two")
    assert logic.first_readable_text(missing, logic.LICENSE_FALLBACK) == (
        logic.LICENSE_FALLBACK
    )
    assert logic.INSTALLER_LICENSE_FALLBACK != logic.LICENSE_FALLBACK


# ------------------------------------------------------------------- version


def test_version_candidates_look_in_the_bundle_then_beside_the_binary(tmp_path):
    candidates = logic.version_candidates(tmp_path)
    assert candidates == (
        logic.payload_app_dir(tmp_path) / logic.VERSION_FILE_NAME,
        tmp_path / logic.PAYLOAD_DIR_NAME / logic.VERSION_FILE_NAME,
        tmp_path / logic.VERSION_FILE_NAME,
    )


def test_first_version_skips_missing_and_empty_files(tmp_path):
    missing = tmp_path / "gone"
    blank = _write(tmp_path / "blank", "   \n")
    real = _write(tmp_path / "real", " 4.1.0\n")
    assert logic.first_version((missing, blank, real)) == "4.1.0"
    assert logic.first_version((missing, blank)) == ""


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("4.1.0", (4, 1, 0)),
        (" 1.2.3 ", (1, 2, 3)),
        ("2.0.0-rc1", (2, 0, 1)),
        ("v3", (3,)),
        ("", (0,)),
    ],
)
def test_version_tuple_reads_the_numeric_parts(version, expected):
    assert logic.version_tuple(version) == expected


def test_compare_versions_orders_by_numeric_parts():
    assert logic.compare_versions("4.0.0", "4.1.0") == -1
    assert logic.compare_versions("4.1.0", "4.1.0") == 0
    assert logic.compare_versions("4.2.0", "4.1.9") == 1


# ---------------------------------------------------------------- user paths


def test_install_and_state_paths_use_the_environment_when_it_is_set(tmp_path):
    local = str(tmp_path / "Local")
    home = tmp_path / "home"
    assert logic.install_target(local, home) == (
        tmp_path / "Local" / "Programs" / logic.APP_NAME
    )
    assert logic.state_dir(local, home) == tmp_path / "Local" / logic.APP_NAME


def test_install_and_state_paths_fall_back_to_the_home_directory(tmp_path):
    home = tmp_path / "home"
    expected = home / "AppData" / "Local"
    assert logic.install_target(None, home).parent.parent == expected
    assert logic.state_dir("", home).parent == expected


def test_start_menu_link_needs_the_roaming_appdata_variable(tmp_path):
    appdata = tmp_path / "Roaming"
    link = logic.start_menu_link(str(appdata))
    assert link == (
        appdata
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / f"{logic.APP_DISPLAY_NAME}.lnk"
    )
    assert logic.start_menu_link(None) is None
    assert logic.start_menu_link("") is None


def test_desktop_link_and_uninstaller_path_sit_where_windows_expects(tmp_path):
    assert logic.desktop_link(tmp_path) == (
        tmp_path / "Desktop" / f"{logic.APP_DISPLAY_NAME}.lnk"
    )
    assert logic.uninstaller_path(tmp_path) == (
        tmp_path / logic.UNINSTALLER_SUBDIR / logic.UNINSTALLER_NAME
    )
