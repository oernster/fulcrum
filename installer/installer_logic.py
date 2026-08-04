"""Installer decisions, with no Qt, no registry and no subprocess.

Everything the installer decides lives here: where files go, which licence
text to read, how two versions compare, what the install state is, what the
uninstall registration should say, what a shortcut or a deferred delete asks
Windows to do. The side effects that carry those decisions out live in
installer_ops.py and the screens that present them live in installer_window.py,
so this module is exercised by the test suite exactly like the application
layer of the app it installs. Nothing here imports from the ``fulcrum``
package (the installer stays standalone) and nothing here reads ``__file__``:
the bundle root is passed in by the entry point, whose location is the one the
onefile bootstrap defines.

British spelling is used in comments. No em dashes appear anywhere.
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Fulcrum"
# Display name shown in all installer UI text and the Apps list. For Fulcrum the
# identifier and the display name match (no embedded space), so the payload
# directory, install path and exe all share the same base name.
APP_DISPLAY_NAME = "Fulcrum"
APP_TAGLINE = "Organisational Decision Architecture Simulation Tool"
APP_PUBLISHER = "Oliver Ernster"
APP_URL = "https://oernster.github.io/fulcrum/"

# Payload layout produced by buildinstaller.py: payload/Fulcrum/ holds the
# bundle's non-binary files (read by the installer UI), payload/Fulcrum.zip the
# full app bundle for deployment and payload/LICENSE the licence text.
PAYLOAD_DIR_NAME = "payload"
MODEL_LICENSE_FILE_NAME = "LICENSE-GPL-3.0.txt"
UI_LICENSE_FILE_NAME = "LICENSE-LGPL-3.0.txt"
INSTALLER_LICENSE_FILE_NAME = "INSTALLER_LICENSE"
VERSION_FILE_NAME = "VERSION"
EXE_NAME = "fulcrum.exe"
# The bundle ships as a single zip because Nuitka's onefile build drops loose
# executables and DLLs from a data directory; the installer extracts it.
PAYLOAD_ARCHIVE_NAME = "Fulcrum.zip"
# The application's asset resolver looks for these beside the executable (the
# bundle root), not in an assets subdirectory. The multi-size .ico is what
# shortcuts and the Apps-list DisplayIcon use, so the small sizes that Windows
# search and the taskbar render are present.
ICON_FILE_NAME = "fulcrum_256.png"
SHORTCUT_ICON_FILE_NAME = "fulcrum.ico"

# Per-user locations (no administrator rights required).
ENV_LOCALAPPDATA = "LOCALAPPDATA"
ENV_APPDATA = "APPDATA"
_PROGRAMS_DIR_NAME = "Programs"
_LOCAL_APPDATA_SUBPATH = ("AppData", "Local")
_START_MENU_SUBPATH = ("Microsoft", "Windows", "Start Menu", "Programs")
_DESKTOP_DIR_NAME = "Desktop"
_SHORTCUT_EXT = ".lnk"
# Per-user state directory the application actually writes: its settings and
# the session autosave, both under a dot-directory in the user's home rather
# than under LocalAppData. This MUST match the app's own directory name or the
# uninstaller's "also remove my settings and saved games" removes nothing and
# says otherwise. tests/installer/test_state_dir.py pins the two together.
_STATE_DIR_NAME = ".fulcrum"

# The registered uninstaller is a copy of this installer placed under the
# install root, so "Apps & features" can re-run it with --uninstall.
UNINSTALLER_SUBDIR = "_uninstall"
UNINSTALLER_NAME = "FulcrumSetup.exe"
UNINSTALL_FLAG = "--uninstall"
# Under a Nuitka onefile build sys.executable is the unpacked temporary
# bootstrap, so the launcher is discovered via this variable instead.
NUITKA_ONEFILE_ENV = "NUITKA_ONEFILE_BINARY"
_EXE_SUFFIX = ".exe"

# HKCU Uninstall registration: this is what makes the app appear in
# "Apps & features" with a working Uninstall button.
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Fulcrum"

# Per-user Run key for launching the app at Windows sign-in (no admin needed).
RUN_SUBKEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "Fulcrum"

# The app registers its notification name and icon under this Application User
# Model ID at startup so Windows can brand its toasts, and the uninstall flow
# removes it. Must match the app's APP_APPUSERMODELID.
APP_AUMID = "uk.codecrafter.fulcrum"
AUMID_CLASSES_SUBKEY = r"Software\Classes\AppUserModelId"

# Crash diagnostics: a console-disabled onefile shows no traceback when it
# dies, so unhandled exceptions are appended to this file under the temp
# directory for the user to send back.
INSTALLER_LOG_NAME = "fulcrum-installer.log"

LICENSE_FALLBACK = "The licence text was not bundled with this installer."
INSTALLER_LICENSE_FALLBACK = (
    "The installer licence notice was not bundled with this installer."
)

_BYTES_PER_KIB = 1024
# Registry value kinds, named here so the decision about what to write stays
# free of winreg; installer_ops maps these to the winreg constants.
REG_SZ = "sz"
REG_DWORD = "dword"

FALLBACK_VERSION = "0.0.0"


@dataclass(frozen=True, slots=True)
class RegistryValue:
    """One value to write under the HKCU uninstall key."""

    name: str
    kind: str
    value: str | int


class AppState:
    """The installed-vs-bundled relationship, driving the primary action."""

    NOT_INSTALLED = "not_installed"
    UPGRADE = "upgrade"
    REINSTALL = "reinstall"
    DOWNGRADE = "downgrade"


# --------------------------------------------------------------------- payload


def payload_app_dir(root: Path) -> Path:
    """Return the bundled application directory inside the payload."""
    return root / PAYLOAD_DIR_NAME / APP_NAME


def payload_archive(root: Path) -> Path:
    """Return the zipped application bundle inside the payload."""
    return root / PAYLOAD_DIR_NAME / PAYLOAD_ARCHIVE_NAME


def licence_candidates(file_name: str, root: Path) -> tuple[Path, ...]:
    """Return where a bundled text file may sit, nearest copy first."""
    return (root / file_name, root / PAYLOAD_DIR_NAME / file_name)


def first_readable_text(candidates: tuple[Path, ...], fallback: str) -> str:
    """Return the first candidate that reads, or the fallback when none do."""
    for candidate in candidates:
        try:
            return candidate.read_text(encoding="utf-8")
        except OSError:
            continue
    return fallback


def version_candidates(root: Path) -> tuple[Path, ...]:
    """Return where the bundled VERSION file may sit, nearest copy first."""
    return (
        payload_app_dir(root) / VERSION_FILE_NAME,
        root / PAYLOAD_DIR_NAME / VERSION_FILE_NAME,
        root / VERSION_FILE_NAME,
    )


def first_version(candidates: tuple[Path, ...]) -> str:
    """Return the first non-empty version text found, or an empty string."""
    for candidate in candidates:
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return ""


# ----------------------------------------------------------------- user paths


def _local_appdata(local_appdata: str | None, home: Path) -> Path:
    if local_appdata:
        return Path(local_appdata)
    return home.joinpath(*_LOCAL_APPDATA_SUBPATH)


def install_target(local_appdata: str | None, home: Path) -> Path:
    """Return the per-user install directory for the application."""
    return _local_appdata(local_appdata, home) / _PROGRAMS_DIR_NAME / APP_NAME


def state_dir(home: Path) -> Path:
    """Return the per-user state directory the app writes (settings, saves)."""
    return home / _STATE_DIR_NAME


def start_menu_link(appdata: str | None) -> Path | None:
    """Return the per-user Start Menu shortcut path, or None when unavailable."""
    if not appdata:
        return None
    programs = Path(appdata).joinpath(*_START_MENU_SUBPATH)
    return programs / f"{APP_DISPLAY_NAME}{_SHORTCUT_EXT}"


def desktop_link(home: Path) -> Path:
    """Return the per-user Desktop shortcut path."""
    return home / _DESKTOP_DIR_NAME / f"{APP_DISPLAY_NAME}{_SHORTCUT_EXT}"


def uninstaller_path(install_dir: Path) -> Path:
    """Return where the registered uninstaller copy lives under an install."""
    return install_dir / UNINSTALLER_SUBDIR / UNINSTALLER_NAME


# ------------------------------------------------------------------ versioning


def version_tuple(version: str) -> tuple[int, ...]:
    """Return a comparable tuple of the numeric parts of a version string."""
    parts: list[int] = []
    for raw in version.strip().split("."):
        digits = "".join(ch for ch in raw if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) if parts else (0,)


def compare_versions(left: str, right: str) -> int:
    """Return -1, 0 or 1 for left < right, left == right or left > right."""
    a = version_tuple(left)
    b = version_tuple(right)
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def detect_state(installed: str | None, location: Path | None, bundled: str) -> str:
    """Classify an existing install against the bundled version."""
    if installed is None or location is None or not location.exists():
        return AppState.NOT_INSTALLED
    comparison = compare_versions(bundled or FALLBACK_VERSION, installed)
    if comparison > 0:
        return AppState.UPGRADE
    if comparison < 0:
        return AppState.DOWNGRADE
    return AppState.REINSTALL


def primary_label(state: str, version: str) -> str:
    """Return the primary button caption for an install state."""
    if state == AppState.NOT_INSTALLED:
        return "Install"
    if state == AppState.UPGRADE:
        return f"Upgrade to {version}" if version else "Upgrade"
    if state == AppState.DOWNGRADE:
        return "Reinstall (older)"
    return "Reinstall"


# -------------------------------------------------------------------- registry


def dir_size_kb(path: Path) -> int | None:
    """Return the total size of a directory in KiB, or None on error."""
    try:
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    except OSError:
        return None
    return total // _BYTES_PER_KIB


def display_icon(install_dir: Path) -> str:
    """Return the Apps-list icon path: the .ico when present, else the exe."""
    icon = install_dir / SHORTCUT_ICON_FILE_NAME
    return str(icon if icon.exists() else install_dir / EXE_NAME)


def uninstall_entry_values(
    install_dir: Path,
    uninstaller: Path,
    version: str,
    estimated_kb: int | None,
) -> tuple[RegistryValue, ...]:
    """Return every value the HKCU Apps and features registration carries."""
    values = [
        RegistryValue("DisplayName", REG_SZ, APP_DISPLAY_NAME),
        RegistryValue("DisplayVersion", REG_SZ, version),
        RegistryValue("InstallLocation", REG_SZ, str(install_dir)),
        RegistryValue("UninstallString", REG_SZ, f'"{uninstaller}" {UNINSTALL_FLAG}'),
        RegistryValue("DisplayIcon", REG_SZ, display_icon(install_dir)),
        RegistryValue("Publisher", REG_SZ, APP_PUBLISHER),
        RegistryValue("URLInfoAbout", REG_SZ, APP_URL),
        RegistryValue("NoModify", REG_DWORD, 1),
        RegistryValue("NoRepair", REG_DWORD, 1),
    ]
    if estimated_kb is not None:
        values.append(RegistryValue("EstimatedSize", REG_DWORD, estimated_kb))
    return tuple(values)


def absolute_location(raw: str | None) -> Path | None:
    """Return a registered install location, or None when it is unusable."""
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else None


def toast_identity_key() -> str:
    """Return the HKCU key holding the app's notification registration."""
    return rf"{AUMID_CLASSES_SUBKEY}\{APP_AUMID}"


# ------------------------------------------------------------------ deployment


def deploy_files(archive: Path, target: Path) -> Path:
    """Extract the bundled application archive to ``target``; return the exe.

    The bundle ships as a single zip because Nuitka's onefile build drops loose
    executables and DLLs from an included data directory. Any previous install
    at the target is removed first so the result is a clean deployment.
    """
    if not archive.is_file():
        raise FileNotFoundError(f"Bundled application not found at {archive}.")
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(target)
    return target / EXE_NAME


def original_installer_exe(
    env_value: str, argv0: str, executable: str, temp_root: Path
) -> Path:
    """Return the original onefile installer the user launched.

    Under a Nuitka onefile build ``sys.executable`` is the unpacked temporary
    bootstrap rather than the launcher; it must not be registered as the
    uninstaller. The real launcher is exposed through the NUITKA_ONEFILE_BINARY
    environment variable and as ``sys.argv[0]``. Prefer those and fall back to
    ``sys.executable`` only when neither resolves to an executable outside the
    temporary directory.
    """
    for raw in (env_value, argv0):
        if not raw:
            continue
        path = Path(raw).resolve()
        if path.suffix.lower() != _EXE_SUFFIX or not path.is_file():
            continue
        if path == temp_root or temp_root in path.parents:
            continue
        return path
    return Path(executable)


def running_from_inside(running_exe: Path, install_dir: Path) -> bool:
    """Return True when the running executable lives inside ``install_dir``."""
    try:
        running = running_exe.resolve()
        root = install_dir.resolve()
    except OSError:
        return True
    return running == root or root in running.parents
