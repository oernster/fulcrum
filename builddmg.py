#!/usr/bin/env python3
"""macOS DMG builder for Fulcrum.

Requires macOS with Xcode command-line tools and Homebrew. Nuitka is the
build-time compiler (from requirements-dev.txt); it produces a standalone .app
bundle, mirroring the Windows Nuitka build. Run from the repository root with
the venv active:

    python builddmg.py

Notarization is mandatory. A Developer ID signature alone is not enough: since
macOS 10.15 Gatekeeper rejects signed-but-unnotarized apps with "Apple could not
verify ... is free of malware". APPLE_ID and APPLE_APP_PASSWORD must be set or
the build stops before doing any work.

Env vars:
    APPLE_ID                  : Apple ID for notarization (required)
    APPLE_APP_PASSWORD        : app-specific password for notarization (required)
    DEVELOPER_ID_APPLICATION  : override the default signing identity
    APPLE_TEAM_ID             : Team ID for notarization (defaults to W7K465GKFJ)
    ALLOW_UNNOTARIZED         : set to 1 to build without notarizing. The result
                                is for local testing only and must never be
                                published as a release artifact.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

from build_utils import require, run, section
from dmg_icon import png_to_icns, set_volume_icon


def _read_version() -> str:
    version_file = Path(__file__).parent / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "0.0.0-dev"


def _resolve_source_png() -> Path | None:
    """The highest-fidelity glow-treated icon PNG present, or None."""
    root = Path(__file__).parent
    for name in SOURCE_PNG_CANDIDATES:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


# Constants

APP_NAME = "Fulcrum"
APP_VERSION = _read_version()
BUNDLE_ID = "uk.codecrafter.Fulcrum"
FINAL_DMG = "fulcrum.dmg"
RW_DMG = "_fulcrum_rw.dmg"
VOLUME_NAME = f"Install {APP_NAME}"
DIST_DIR = Path("dist")

# Source PNG for the macOS .icns. This must be one of the glow-treated icons
# generate_icons.py emits, NOT the fulcrum.png master: that master is the raw
# dark-on-black artwork, so building the icns from it ships the pre-glow icon
# (dark art on a dark fill) while Windows (fulcrum.ico) and Flatpak
# (fulcrum_*.png) ship the treated set. Ordered largest first so png_to_icns
# downscales from the highest-fidelity treated source that is present.
SOURCE_PNG_CANDIDATES = (
    "fulcrum_1024.png",
    "fulcrum_512.png",
    "fulcrum_256.png",
)

# Dark background matching Fulcrum's theme base colour (the installer _BACKGROUND
# and theme.py dark surface), so transparent icon areas read dark, not white.
ICON_BG = (0x0D, 0x0F, 0x12)

# Per-resolution PNGs plus the loose assets the resource resolver looks for
# beside the binary (icon, the amber spinbox arrows). The book covers under
# assets/books are added separately as a data directory.
BUNDLED_ICONS = [
    "fulcrum_16.png",
    "fulcrum_32.png",
    "fulcrum_48.png",
    "fulcrum_64.png",
    "fulcrum_128.png",
    "fulcrum_256.png",
    "fulcrum_provenance_256.png",
    "fulcrum_512.png",
    "fulcrum.png",
    "fulcrum.ico",
    "spin_up.png",
    "spin_down.png",
]

# VERSION plus the dual-licence texts (model GPL-3.0, UI LGPL-3.0) and the
# overview, all resolved beside the binary by fulcrum.shared.resources.
BUNDLED_DATA = [
    "VERSION",
    "LICENSE",
    "LICENSE-GPL-3.0.txt",
    "LICENSE-LGPL-3.0.txt",
]

# Book covers shown by Help > Book background, staged under assets/books so
# find_book_cover resolves them in the frozen build.
BOOK_COVER_DIR = "assets/books"

# Generated header-button icons, staged under assets/buttons so
# find_button_icon resolves them in the frozen build.
BUTTON_ICON_DIR = "assets/buttons"

# Calibration examples offered by Organisation > Open example organisation.
EXAMPLES_DIR = "examples/calibration"

DEVELOPER_ID = os.environ.get(
    "DEVELOPER_ID_APPLICATION",
    "Developer ID Application: Oliver Ernster (W7K465GKFJ)",
)
APPLE_ID = os.environ.get("APPLE_ID", "")
APPLE_APP_PASSWORD = os.environ.get("APPLE_APP_PASSWORD", "")
APPLE_TEAM_ID = os.environ.get("APPLE_TEAM_ID", "W7K465GKFJ")

# The notarization credential for this app, created once with
#   xcrun notarytool store-credentials Fulcrum \
#     --apple-id <id> --team-id <team> --password <app-specific>
# One profile per app means a leaked credential can be revoked for a single
# app. Stated explicitly rather than derived from a display name: the profile
# is a fact registered with Apple, and deriving it would silently change which
# credential the build looks for if that name were ever edited.
# APPLE_KEYCHAIN_PROFILE overrides it.
NOTARY_PROFILE = os.environ.get("APPLE_KEYCHAIN_PROFILE", "") or "Fulcrum"

# The notary service accepts only an app-specific password from appleid.apple.com
# and rejects the Apple account password with HTTP 401. The shape is distinctive,
# so it is checked before the build rather than discovered after it.
APP_SPECIFIC_PASSWORD_RE = re.compile(r"^[a-z]{4}-[a-z]{4}-[a-z]{4}-[a-z]{4}$")

# Escape hatch for local test builds. Distribution builds must never set this:
# an unnotarized DMG is rejected by Gatekeeper on every machine but the one that
# signed it, and the failure is invisible at build time.
ALLOW_UNNOTARIZED = os.environ.get("ALLOW_UNNOTARIZED", "") == "1"
# Notarization is the default and the keychain profile always resolves, so the
# only way to skip it is to ask for that explicitly.
NOTARIZING = not ALLOW_UNNOTARIZED

# create-dmg window layout (Finder coordinates), named so they are not magic.
DMG_WINDOW_POS = ("200", "120")
DMG_WINDOW_SIZE = ("640", "400")
DMG_ICON_SIZE = "100"
DMG_TEXT_SIZE = "14"
DMG_APP_DROP_POS = ("520", "180")
DMG_APP_ICON_POS = ("120", "180")

# create-dmg returns 2 when it succeeds but cannot set a custom window
# background; that is not a failure for a headless build.
DMG_OK_RETURN_CODES = (0, 2)
BYTES_PER_MB = 1024 * 1024

# Minimal hardened-runtime entitlements. Fulcrum is a local-first app with no
# network use and no JIT, so none of the relaxed memory/network entitlements are
# required. disable-library-validation lets the hardened runtime load the
# Nuitka-bundled Qt frameworks signed with our identity.
ENTITLEMENTS = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
</dict>
</plist>
"""


# Steps


def check_platform() -> None:
    section("Platform check")
    if sys.platform != "darwin":
        sys.exit("ERROR: This script must run on macOS.")
    result = subprocess.run(
        ["sw_vers", "-productVersion"], capture_output=True, text=True, check=False
    )
    print(f"  macOS {result.stdout.strip()}")
    try:
        import nuitka  # noqa: F401
    except ImportError:
        sys.exit("ERROR: Nuitka not installed. Run: pip install nuitka")
    require("create-dmg", "create-dmg")
    require("codesign")
    print("  All tools present.")


def check_notarization_credentials() -> None:
    """Fail before the build starts if the release cannot be notarized.

    Checked up front rather than at the notarization step so a missing password
    costs seconds instead of a full PyInstaller run.
    """
    section("Notarization credentials")
    if ALLOW_UNNOTARIZED:
        print("  WARNING: ALLOW_UNNOTARIZED=1 set.")
        print("  WARNING: this build is for local testing and must not be released.")
        return
    if APPLE_ID and APPLE_APP_PASSWORD:
        if not APP_SPECIFIC_PASSWORD_RE.match(APPLE_APP_PASSWORD):
            sys.exit(
                "ERROR: APPLE_APP_PASSWORD is not an app-specific password.\n"
                "  Expected four lowercase groups of four, like abcd-efgh-ijkl-mnop.\n"
                "  An Apple account password is rejected by the notary service with\n"
                "  'HTTP status code: 401. Invalid credentials'.\n"
                "  Generate one at https://appleid.apple.com (Sign-In and Security,\n"
                "  App-Specific Passwords), or leave both variables unset and store\n"
                f"  the credential in the keychain as profile {NOTARY_PROFILE}."
            )
        print(f"  Notarizing as {APPLE_ID} (team {APPLE_TEAM_ID}).")
        return
    print(f"  Notarizing with keychain profile {NOTARY_PROFILE}.")


def check_runtime_dependencies() -> None:
    """Fail if anything in requirements.txt is absent from the build interpreter.

    PyInstaller only warns when --collect-submodules names a package it cannot
    find, so a stale venv yields a bundle that builds, signs and notarizes
    cleanly and then dies at launch with ModuleNotFoundError. Checking the
    interpreter that is about to be frozen turns a silent runtime failure into a
    build failure.
    """
    section("Runtime dependencies")
    requirements = Path(__file__).parent / "requirements.txt"
    if not requirements.exists():
        sys.exit(f"ERROR: {requirements.name} not found beside builddmg.py.")

    missing: list[str] = []
    checked = 0
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        # Skip blanks and pip options such as -r or --index-url. Distribution
        # names are what requirements.txt lists, so no import-name mapping is
        # needed: PySide6 and pyobjc-framework-Cocoa both resolve here.
        if not line or line.startswith("-"):
            continue
        try:
            requirement = Requirement(line)
        except InvalidRequirement as error:
            sys.exit(f"ERROR: cannot parse '{line}' in {requirements.name}: {error}")
        # An environment marker such as sys_platform == "win32" means the package
        # is not wanted on this platform, so its absence is correct rather than a
        # fault. Evaluating the marker beats naming Windows packages here, which
        # would go stale the moment the requirements change.
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        checked += 1
        try:
            metadata.version(requirement.name)
        except metadata.PackageNotFoundError:
            missing.append(requirement.name)

    if missing:
        sys.exit(
            "ERROR: the build interpreter is missing "
            f"{len(missing)} of {checked} requirements:\n"
            + "".join(f"    {name}\n" for name in missing)
            + "  PyInstaller would omit them and the app would crash at launch\n"
            "  with ModuleNotFoundError. Install them first:\n"
            f"    pip install -r {requirements.name}"
        )
    print(f"  All {checked} requirements present.")


def notarytool_credentials() -> list[str]:
    """Authentication arguments for notarytool.

    An explicit APPLE_ID and APPLE_APP_PASSWORD pair wins, for CI that has no
    keychain. Otherwise the per-app profile is used, which keeps the secret out
    of the process arguments where any other process could read it via ps.
    """
    if APPLE_ID and APPLE_APP_PASSWORD:
        return [
            "--apple-id",
            APPLE_ID,
            "--password",
            APPLE_APP_PASSWORD,
            "--team-id",
            APPLE_TEAM_ID,
        ]
    return ["--keychain-profile", NOTARY_PROFILE]


def redact(cmd: list[str]) -> str:
    """Render a command with the value after --password masked.

    run() echoes every command it runs, and CalledProcessError repeats the whole
    argument list in its traceback. Both would otherwise copy the app-specific
    password into build logs and CI output.
    """
    parts: list[str] = []
    mask_next = False
    for arg in (str(c) for c in cmd):
        parts.append("********" if mask_next else arg)
        mask_next = arg == "--password"
    return " ".join(parts)


def notarytool_submit(target: Path) -> None:
    """Submit target to Apple and wait for the verdict.

    A failed submission stops the build rather than producing an artifact that
    looks distributable. subprocess is called directly instead of through run()
    so that neither the echoed command nor the failure path exposes the
    password. Stapling is a separate step because the submitted file and the
    file that carries the ticket differ for a .app (a zip is submitted, the
    bundle is stapled).
    """
    cmd = [
        "xcrun",
        "notarytool",
        "submit",
        str(target),
        *notarytool_credentials(),
        "--wait",
    ]
    print(f"  $ {redact(cmd)}")
    if subprocess.run(cmd, check=False).returncode == 0:
        return
    sys.exit(
        "ERROR: notarization failed (notarytool output above).\n"
        "  'No Keychain password item found' means this app has no stored\n"
        "  credential yet. Generate an app-specific password at\n"
        "  https://appleid.apple.com (Sign-In and Security), then:\n"
        f"    xcrun notarytool store-credentials {NOTARY_PROFILE} \\\n"
        "      --apple-id you@example.com --team-id "
        f"{APPLE_TEAM_ID} --password <app-specific>\n"
        "  'HTTP status code: 401' means the credential is wrong: use an\n"
        "  app-specific password, not your Apple account password.\n"
        "  For an 'Invalid' verdict, the per-binary reasons are in:\n"
        "    xcrun notarytool log <submission-id> "
        f"--keychain-profile {NOTARY_PROFILE}"
    )


def clean() -> None:
    section("Clean previous build")
    for path in [
        "dist",
        FINAL_DMG,
        "_dmg_staging",
        RW_DMG,
    ]:
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            print(f"  Removed: {path}")


def build_app_bundle(icns_path: Path | None = None) -> Path:
    section("Nuitka: build .app bundle")

    root = Path(__file__).parent
    jobs = str(os.cpu_count() or 1)

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--enable-plugin=pyside6",
        "--macos-create-app-bundle",
        "--macos-app-mode=gui",
        f"--macos-app-name={APP_NAME}",
        f"--macos-app-version={APP_VERSION}",
        f"--macos-signed-app-name={BUNDLE_ID}",
        f"--jobs={jobs}",
        f"--output-dir={DIST_DIR}",
    ]
    if icns_path:
        cmd.append(f"--macos-app-icon={icns_path}")

    # Bundle the loose data files and per-size icons beside the binary, plus the
    # book covers under assets/books. The resource resolver finds them beside
    # the executable (Contents/MacOS) or in Contents/Resources.
    for name in (*BUNDLED_DATA, *BUNDLED_ICONS):
        asset = root / name
        if asset.exists():
            cmd.append(f"--include-data-file={asset}={name}")
    books = root / "assets" / "books"
    if books.is_dir():
        for cover in sorted(books.glob("*.png")):
            cmd.append(f"--include-data-file={cover}={BOOK_COVER_DIR}/{cover.name}")
    buttons = root / "assets" / "buttons"
    if buttons.is_dir():
        for icon in sorted(buttons.glob("*.png")):
            cmd.append(f"--include-data-file={icon}={BUTTON_ICON_DIR}/{icon.name}")
    calibration = root / "examples" / "calibration"
    if calibration.is_dir():
        for example in sorted(calibration.glob("*.json")):
            cmd.append(
                f"--include-data-file={example}=" f"{EXAMPLES_DIR}/{example.name}"
            )

    cmd.append(str(root / "main.py"))

    run(cmd)

    app_path = DIST_DIR / f"{APP_NAME}.app"
    if not app_path.exists():
        # Nuitka may name the bundle after the entry script; normalise it.
        produced = sorted(DIST_DIR.rglob("*.app"))
        if not produced:
            sys.exit(f"ERROR: no .app produced under {DIST_DIR}")
        shutil.move(str(produced[0]), str(app_path))
    print(f"  Built: {app_path}")
    return app_path


def strip_build_artifacts(app_path: Path) -> None:
    section("Strip build artifacts")
    # PySide6 ships .cpp.o object files inside its QML plugin directories. They
    # are Mach-O relocatable binaries that codesign --deep silently skips but
    # Gatekeeper flags as unsigned, causing the entire bundle to be rejected.
    removed = 0
    for f in app_path.rglob("*.o"):
        if f.is_file():
            f.unlink()
            removed += 1
    for d in sorted(app_path.rglob("objects-*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    print(f"  Removed {removed} intermediate object file(s)")


def sign_bundle(app_path: Path, entitlements_path: Path) -> None:
    section("Code signing")

    run(
        [
            "codesign",
            "--force",
            "--deep",
            "--options",
            "runtime",
            "--entitlements",
            str(entitlements_path),
            "--sign",
            DEVELOPER_ID,
            str(app_path),
        ]
    )

    run(["codesign", "--verify", "--deep", "--strict", str(app_path)])
    print("  Signature verified.")


def notarize_bundle(app_path: Path) -> None:
    """Notarize and staple the .app before it is placed in the DMG.

    Stapling only the DMG leaves the copied-out .app with no local ticket, so
    Gatekeeper falls back to an online check and the app fails to launch for a
    user who is offline or behind a restrictive network. notarytool only accepts
    archives, so the bundle is zipped with ditto first (ditto preserves the
    symlinks and metadata the embedded signature depends on); the ticket is then
    stapled to the bundle itself, since a zip cannot carry one.
    """
    if not NOTARIZING:
        return
    section("Notarize .app bundle")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / f"{APP_NAME}.zip"
        run(["ditto", "-c", "-k", "--keepParent", str(app_path), str(archive)])
        notarytool_submit(archive)
    run(["xcrun", "stapler", "staple", str(app_path)])
    print("  Bundle notarized and stapled.")


def create_dmg(app_path: Path) -> None:
    section("Create DMG")

    staging = Path("_dmg_staging")
    staging.mkdir(exist_ok=True)
    dest = staging / app_path.name
    if dest.exists():
        shutil.rmtree(dest)
    # ditto preserves the symlinks macOS frameworks rely on (for example
    # Python.framework/Python -> Versions/Current/Python). Dereferencing them
    # into regular files invalidates every embedded code signature and causes
    # dlopen failures at runtime.
    run(["ditto", str(app_path), str(dest)])

    if os.path.exists(FINAL_DMG):
        os.remove(FINAL_DMG)

    cmd = [
        "create-dmg",
        "--volname",
        VOLUME_NAME,
        "--window-pos",
        *DMG_WINDOW_POS,
        "--window-size",
        *DMG_WINDOW_SIZE,
        "--icon-size",
        DMG_ICON_SIZE,
        "--text-size",
        DMG_TEXT_SIZE,
        "--app-drop-link",
        *DMG_APP_DROP_POS,
        "--icon",
        f"{APP_NAME}.app",
        *DMG_APP_ICON_POS,
        FINAL_DMG,
        str(staging / f"{APP_NAME}.app"),
    ]

    result = run(cmd, check=False)
    if result.returncode not in DMG_OK_RETURN_CODES:
        sys.exit(f"ERROR: create-dmg failed (exit {result.returncode})")

    shutil.rmtree(staging)
    print(f"  DMG created: {FINAL_DMG}")


def sign_dmg() -> None:
    section("Sign DMG")
    run(["codesign", "--force", "--sign", DEVELOPER_ID, FINAL_DMG])
    print("  DMG signed.")


def notarize_dmg() -> None:
    if not NOTARIZING:
        return
    section("Notarize DMG")
    notarytool_submit(Path(FINAL_DMG))
    run(["xcrun", "stapler", "staple", FINAL_DMG])
    print("  Notarization complete and stapled.")


def verify_dmg() -> None:
    section("Verify DMG")
    run(["codesign", "--verify", FINAL_DMG])
    if not NOTARIZING:
        size_mb = os.path.getsize(FINAL_DMG) / (1024 * 1024)
        print(f"  {FINAL_DMG}  ({size_mb:.1f} MB): UNNOTARIZED, local testing only")
        return
    # stapler validate proves a ticket is attached; spctl replays the check
    # Gatekeeper performs on the end user's machine. Together they catch the
    # silent case where signing succeeded but notarization never happened.
    run(["xcrun", "stapler", "validate", FINAL_DMG])
    run(["spctl", "--assess", "--type", "install", "-vv", FINAL_DMG])
    size_mb = os.path.getsize(FINAL_DMG) / (1024 * 1024)
    print(f"  {FINAL_DMG}  ({size_mb:.1f} MB): notarized, ready for distribution")


def apply_file_icon(png_path: Path) -> None:
    section("Apply file icon")
    require("fileicon")
    run(["fileicon", "set", FINAL_DMG, str(png_path)])
    print(f"  Icon applied to {FINAL_DMG}")


# Main


def main() -> int:
    print(f"\nFULCRUM DMG BUILDER  v{APP_VERSION}")
    print(f"Signing identity: {DEVELOPER_ID}")

    check_platform()
    check_runtime_dependencies()
    check_notarization_credentials()
    clean()

    with tempfile.NamedTemporaryFile(
        suffix=".entitlements", mode="w", delete=False
    ) as f:
        f.write(ENTITLEMENTS)
        entitlements_path = Path(f.name)

    with tempfile.TemporaryDirectory() as icon_tmp:
        png_path = _resolve_source_png()
        icns_path = png_to_icns(png_path, Path(icon_tmp), ICON_BG) if png_path else None
        if not icns_path:
            print(
                "  WARNING: no glow-treated icon PNG found "
                f"({', '.join(SOURCE_PNG_CANDIDATES)}); "
                "run generate_icons.py. Building without custom icon."
            )

        try:
            app_path = build_app_bundle(icns_path)
            strip_build_artifacts(app_path)
            sign_bundle(app_path, entitlements_path)
            notarize_bundle(app_path)
            create_dmg(app_path)
            # Both icon steps rewrite the DMG, so they run before it is signed
            # and notarized. Doing either afterwards would modify a file that
            # Gatekeeper has already been told the hash of.
            if icns_path:
                set_volume_icon(icns_path, FINAL_DMG, RW_DMG)
                apply_file_icon(png_path)
            sign_dmg()
            notarize_dmg()
            verify_dmg()
        finally:
            entitlements_path.unlink(missing_ok=True)

    print(f"\nDone. Distribute: {FINAL_DMG}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
