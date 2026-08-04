"""Tests for the installer's state, registration, shell-out and deploy rules.

These are the decisions a defect in which lands on a user's machine before
the application ever starts: what "Apps & features" is told, what PowerShell
is asked to do and what a deploy leaves behind.
"""

import zipfile
from pathlib import Path

import pytest

import installer_logic as logic
import installer_scripts as scripts


class _UnreadableDirectory:
    """A directory-like whose walk fails, standing in for a denied path."""

    def rglob(self, _pattern):
        raise OSError("access denied")


class _UnresolvablePath:
    """A path-like whose resolution fails, standing in for a broken link."""

    def resolve(self):
        raise OSError("cannot resolve")


def _values(entries):
    return {entry.name: entry.value for entry in entries}


# --------------------------------------------------------------- app state


def test_a_missing_registration_or_location_reads_as_not_installed(tmp_path):
    present = tmp_path / "install"
    present.mkdir()
    assert logic.detect_state(None, present, "4.1.0") == logic.AppState.NOT_INSTALLED
    assert logic.detect_state("4.0.0", None, "4.1.0") == logic.AppState.NOT_INSTALLED
    gone = tmp_path / "gone"
    assert logic.detect_state("4.0.0", gone, "4.1.0") == logic.AppState.NOT_INSTALLED


@pytest.mark.parametrize(
    ("installed", "bundled", "expected"),
    [
        ("4.0.0", "4.1.0", logic.AppState.UPGRADE),
        ("4.1.0", "4.1.0", logic.AppState.REINSTALL),
        ("4.2.0", "4.1.0", logic.AppState.DOWNGRADE),
    ],
)
def test_an_existing_install_is_classified_against_the_bundle(
    tmp_path, installed, bundled, expected
):
    location = tmp_path / "install"
    location.mkdir()
    assert logic.detect_state(installed, location, bundled) == expected


def test_an_unreadable_bundle_version_is_treated_as_the_oldest(tmp_path):
    location = tmp_path / "install"
    location.mkdir()
    assert logic.detect_state("4.1.0", location, "") == logic.AppState.DOWNGRADE
    assert logic.FALLBACK_VERSION == "0.0.0"


@pytest.mark.parametrize(
    ("state", "version", "expected"),
    [
        (logic.AppState.NOT_INSTALLED, "4.1.0", "Install"),
        (logic.AppState.UPGRADE, "4.1.0", "Upgrade to 4.1.0"),
        (logic.AppState.UPGRADE, "", "Upgrade"),
        (logic.AppState.DOWNGRADE, "4.1.0", "Reinstall (older)"),
        (logic.AppState.REINSTALL, "4.1.0", "Reinstall"),
    ],
)
def test_the_primary_button_says_what_it_will_do(state, version, expected):
    assert logic.primary_label(state, version) == expected


# ---------------------------------------------------------------- registry


def test_directory_size_is_reported_in_kibibytes(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "a.bin").write_bytes(b"x" * 2048)
    (tmp_path / "b.bin").write_bytes(b"x" * 1024)
    assert logic.dir_size_kb(tmp_path) == 3


def test_an_unwalkable_directory_reports_no_size():
    assert logic.dir_size_kb(_UnreadableDirectory()) is None


def test_the_apps_list_icon_prefers_the_multi_size_ico(tmp_path):
    assert logic.display_icon(tmp_path) == str(tmp_path / logic.EXE_NAME)
    (tmp_path / logic.SHORTCUT_ICON_FILE_NAME).write_bytes(b"ico")
    assert logic.display_icon(tmp_path) == str(tmp_path / logic.SHORTCUT_ICON_FILE_NAME)


def test_the_uninstall_registration_carries_a_working_uninstall_string(tmp_path):
    uninstaller = logic.uninstaller_path(tmp_path)
    entries = logic.uninstall_entry_values(tmp_path, uninstaller, "4.1.0", 4096)
    values = _values(entries)
    assert values["DisplayName"] == logic.APP_DISPLAY_NAME
    assert values["DisplayVersion"] == "4.1.0"
    assert values["InstallLocation"] == str(tmp_path)
    assert values["UninstallString"] == f'"{uninstaller}" {logic.UNINSTALL_FLAG}'
    assert values["Publisher"] == logic.APP_PUBLISHER
    assert values["URLInfoAbout"] == logic.APP_URL
    assert values["EstimatedSize"] == 4096
    kinds = {entry.name: entry.kind for entry in entries}
    assert kinds["NoModify"] == logic.REG_DWORD
    assert kinds["DisplayName"] == logic.REG_SZ


def test_an_unknown_size_leaves_the_estimated_size_value_out(tmp_path):
    entries = logic.uninstall_entry_values(tmp_path, tmp_path / "u.exe", "4.1.0", None)
    assert "EstimatedSize" not in _values(entries)


@pytest.mark.parametrize("raw", [None, "", "relative\\path"])
def test_an_unusable_registered_location_is_refused(raw):
    assert logic.absolute_location(raw) is None


def test_an_absolute_registered_location_is_accepted(tmp_path):
    assert logic.absolute_location(str(tmp_path)) == Path(str(tmp_path))


def test_the_toast_identity_key_sits_under_the_classes_subkey():
    assert logic.toast_identity_key() == (
        rf"{logic.AUMID_CLASSES_SUBKEY}\{logic.APP_AUMID}"
    )


# ------------------------------------------------------------ shell-out text


def test_the_shortcut_command_points_at_the_installed_exe(tmp_path):
    exe = tmp_path / logic.EXE_NAME
    link = tmp_path / "Fulcrum.lnk"
    command = scripts.shortcut_command(exe, link)
    assert f"$s.TargetPath = '{exe}'" in command
    assert f"$s.WorkingDirectory = '{tmp_path}'" in command
    assert "IconLocation" not in command


def test_the_shortcut_command_carries_the_icon_when_one_is_deployed(tmp_path):
    icon = tmp_path / logic.SHORTCUT_ICON_FILE_NAME
    icon.write_bytes(b"ico")
    command = scripts.shortcut_command(tmp_path / logic.EXE_NAME, tmp_path / "F.lnk")
    assert f"$s.IconLocation = '{icon}'" in command


def test_the_deferred_delete_escapes_quotes_and_polls_the_lock(tmp_path):
    quoted = tmp_path / "Ol'iver"
    script = scripts.deferred_delete_script(quoted)
    assert "Ol''iver" in script
    assert "Remove-Item -LiteralPath $d -Recurse -Force" in script
    assert "Start-Sleep -Milliseconds" in script


def test_the_task_list_is_read_case_insensitively():
    assert scripts.process_is_running("FULCRUM.EXE  1234 Console") is True
    assert scripts.process_is_running("No tasks are running") is False


# ------------------------------------------------------------------- deploy


def _archive(tmp_path, name=logic.PAYLOAD_ARCHIVE_NAME):
    archive = tmp_path / name
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(logic.EXE_NAME, "binary")
        bundle.writestr("assets/fulcrum.ico", "icon")
    return archive


def test_deploying_extracts_the_bundle_and_returns_the_exe(tmp_path):
    archive = _archive(tmp_path)
    target = tmp_path / "install"
    exe = logic.deploy_files(archive, target)
    assert exe == target / logic.EXE_NAME
    assert exe.read_text(encoding="utf-8") == "binary"
    assert (target / "assets" / "fulcrum.ico").is_file()


def test_deploying_over_an_existing_install_leaves_nothing_of_the_old_one(tmp_path):
    archive = _archive(tmp_path)
    target = tmp_path / "install"
    target.mkdir()
    stale = target / "stale.dll"
    stale.write_text("old", encoding="utf-8")
    logic.deploy_files(archive, target)
    assert not stale.exists()


def test_deploying_without_a_bundled_archive_says_so(tmp_path):
    with pytest.raises(FileNotFoundError):
        logic.deploy_files(tmp_path / "missing.zip", tmp_path / "install")


# -------------------------------------------------------- the running binary


def test_the_onefile_launcher_is_preferred_over_the_unpacked_bootstrap(tmp_path):
    temp_root = (tmp_path / "temp").resolve()
    temp_root.mkdir()
    bootstrap = temp_root / "bootstrap.exe"
    bootstrap.write_bytes(b"exe")
    launcher = tmp_path / "FulcrumSetup.exe"
    launcher.write_bytes(b"exe")
    found = logic.original_installer_exe(
        str(launcher), str(bootstrap), str(bootstrap), temp_root
    )
    assert found == launcher.resolve()


def test_a_launcher_inside_the_temporary_directory_is_rejected(tmp_path):
    temp_root = (tmp_path / "temp").resolve()
    temp_root.mkdir()
    bootstrap = temp_root / "bootstrap.exe"
    bootstrap.write_bytes(b"exe")
    fallback = tmp_path / "python.exe"
    found = logic.original_installer_exe("", str(bootstrap), str(fallback), temp_root)
    assert found == fallback


def test_a_candidate_that_is_not_an_existing_exe_is_rejected(tmp_path):
    temp_root = (tmp_path / "temp").resolve()
    temp_root.mkdir()
    script = tmp_path / "app.py"
    script.write_text("x", encoding="utf-8")
    fallback = tmp_path / "python.exe"
    found = logic.original_installer_exe(
        str(script), str(tmp_path / "gone.exe"), str(fallback), temp_root
    )
    assert found == fallback


def test_the_temporary_root_itself_is_never_registered(tmp_path):
    temp_root = tmp_path / "temp.exe"
    temp_root.write_bytes(b"exe")
    fallback = tmp_path / "python.exe"
    found = logic.original_installer_exe(
        str(temp_root), "", str(fallback), temp_root.resolve()
    )
    assert found == fallback


def test_an_uninstaller_inside_the_install_defers_its_own_removal(tmp_path):
    install_dir = tmp_path / "install"
    inside = install_dir / logic.UNINSTALLER_SUBDIR / logic.UNINSTALLER_NAME
    inside.parent.mkdir(parents=True)
    inside.write_bytes(b"exe")
    assert logic.running_from_inside(inside, install_dir) is True
    assert logic.running_from_inside(install_dir, install_dir) is True
    assert logic.running_from_inside(tmp_path / "other.exe", install_dir) is False


def test_an_unresolvable_executable_defers_rather_than_deleting(tmp_path):
    assert logic.running_from_inside(_UnresolvablePath(), tmp_path) is True
