#!/usr/bin/env bash
# build_flatpak.sh - Build Fulcrum as a Flatpak
#
# Uses org.freedesktop.Platform//25.08 (Python 3.13, glibc 2.42). Fulcrum is a
# pure PySide6 desktop app: no native toolchains, no model downloads, no network
# at runtime. Its single wheel set (PySide6 plus shiboken6) is pre-downloaded on
# the host, then installed inside the sandbox from those local wheels with
# --no-index, so the build itself is offline.
#
# Usage:
#   ./build_flatpak.sh             - build, install locally, AND produce fulcrum.flatpak
#   ./build_flatpak.sh --no-bundle - build + install only (skip the distributable bundle)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/venv/bin/activate"

APP_ID="uk.codecrafter.Fulcrum"
APP_VERSION=$(tr -d '[:space:]' < VERSION)
BUNDLE="fulcrum.flatpak"
BUILD_DIR=".flatpak-build"
REPO_DIR=".flatpak-repo"
MANIFEST="${APP_ID}.yml"

# Where the app source is staged inside the sandbox. The package directory and
# main.py both live here; the launcher puts it on PYTHONPATH so "import fulcrum"
# resolves and the resource resolver finds the loose assets beside main.py.
SHARE_DIR="fulcrum"

RUNTIME="org.freedesktop.Platform"
SDK="org.freedesktop.Sdk"
RUNTIME_VERSION="25.08"

# Python version shipped by the runtime above. Used to build the site-packages
# path the launcher exports; keep it in sync with RUNTIME_VERSION.
PYTHON_MM="3.13"

# Wheels are tagged for the runtime's Python and glibc. manylinux_2_34 is the tag
# PySide6's cp-abi3 wheels use; pip expands it to also accept every lower
# manylinux tag, so this single target covers PySide6 and shiboken6.
WHEEL_PYTHON="3.13"
WHEEL_PLATFORM="manylinux_2_34_x86_64"

# The distributable bundle is the whole point of this script, so it is built by
# default. Pass --no-bundle to skip it and only build + install locally.
MAKE_BUNDLE=1
for arg in "$@"; do [[ "$arg" == "--no-bundle" ]] && MAKE_BUNDLE=0; done

# Colour helpers
bold=$(tput bold 2>/dev/null || true)
reset=$(tput sgr0 2>/dev/null || true)
section() { echo; echo "${bold}=== $* ===${reset}"; }

run_with_spinner() {
    local label="$1" watch=""
    shift
    if [[ "${1:-}" == "--watch" ]]; then watch="$2"; shift 2; fi
    [[ "${1:-}" == "--" ]] && shift
    "$@" &
    local pid=$! i=0 spin='⣾⣽⣻⢿⡿⣟⣯⣷'
    while kill -0 "$pid" 2>/dev/null; do
        local extra=""
        if [[ -n "$watch" && -f "$watch" ]]; then
            extra="  ($(du -sh "$watch" 2>/dev/null | cut -f1) written)"
        fi
        printf "\r  %s  %s%s" "${spin:$((i % ${#spin})):1}" "$label" "$extra"
        i=$((i + 1)); sleep 0.3
    done
    wait "$pid"; local rc=$?
    [[ $rc -eq 0 ]] && printf "\r  ✓  %-72s\n" "$label" \
                     || printf "\r  ✗  %-72s\n" "$label"
    return $rc
}

# Tool checks
section "Checking dependencies"
install_if_missing() {
    local pkg="$1"
    if ! command -v "$pkg" &>/dev/null; then
        echo "  $pkg not found - installing..."
        if   command -v apt-get &>/dev/null; then sudo apt-get update -qq && sudo apt-get install -y "$pkg"
        elif command -v dnf    &>/dev/null; then sudo dnf install -y "$pkg"
        elif command -v pacman &>/dev/null; then sudo pacman -Sy --noconfirm "$pkg"
        else echo "ERROR: unsupported package manager" >&2; exit 1; fi
    else echo "  $pkg: OK"; fi
}
install_if_missing flatpak
install_if_missing flatpak-builder

# Flatpak remote + runtime
section "Configuring Flathub remote"
flatpak remote-add --if-not-exists --user flathub \
    https://dl.flathub.org/repo/flathub.flatpakrepo

section "Installing runtime and SDK (${RUNTIME_VERSION})"
flatpak install --user --noninteractive flathub \
    "${RUNTIME}//${RUNTIME_VERSION}" \
    "${SDK}//${RUNTIME_VERSION}" \
    || true

# Pre-download wheels (Python 3.13 / manylinux x86_64). Downloading on the host
# avoids slow sandboxed network calls and lets the sandbox install with
# --no-index (fully offline build). Dependencies are resolved here so PySide6's
# Essentials/Addons sub-wheels come along too.
section "Pre-downloading wheels (Python ${WHEEL_PYTHON} / ${WHEEL_PLATFORM})"
rm -rf .flatpak-wheels
mkdir -p .flatpak-wheels

run_with_spinner "Downloading wheels for $(grep -cE '^[^#[:space:]]' requirements.txt) requirements" -- \
    pip download --only-binary :all: \
        --python-version "${WHEEL_PYTHON}" --implementation cp \
        --platform "${WHEEL_PLATFORM}" \
        -q -d .flatpak-wheels -r requirements.txt

echo "  $(ls .flatpak-wheels/ | wc -l) distributions ready"

# Packaging helpers
section "Writing packaging helpers"
mkdir -p packaging

# site-packages path matches the runtime's Python version. Fulcrum reads and
# writes plan JSON and HTML files the user chooses, which the --filesystem=home
# permission below makes reachable, so no user-dirs override env var is needed.
cat > packaging/fulcrum-launcher.sh <<LAUNCHER
#!/bin/sh
export LD_LIBRARY_PATH="/app/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
export PYTHONPATH="/app/share/${SHARE_DIR}:/app/lib/python${PYTHON_MM}/site-packages\${PYTHONPATH:+:\$PYTHONPATH}"
export QT_PLUGIN_PATH="/app/lib/python${PYTHON_MM}/site-packages/PySide6/Qt/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="/app/lib/python${PYTHON_MM}/site-packages/PySide6/Qt/plugins/platforms"
export QML2_IMPORT_PATH="/app/lib/python${PYTHON_MM}/site-packages/PySide6/Qt/qml"
if [ -n "\${WAYLAND_DISPLAY:-}" ] && [ -z "\${FORCE_X11:-}" ]; then
    export QT_QPA_PLATFORM=wayland
elif [ -n "\${DISPLAY:-}" ]; then
    export QT_QPA_PLATFORM=xcb
else
    export QT_QPA_PLATFORM=xcb
fi
exec python3 /app/share/${SHARE_DIR}/main.py "\$@"
LAUNCHER
chmod +x packaging/fulcrum-launcher.sh

cat > "packaging/${APP_ID}.desktop" <<DESKTOP
[Desktop Entry]
Name=Fulcrum
Comment=Organisational Decision Architecture Sandbox
Exec=fulcrum
Icon=${APP_ID}
Terminal=false
Type=Application
Categories=Education;Office;
Keywords=decision;architecture;organisation;strategy;sandbox;
DESKTOP

cat > "packaging/${APP_ID}.metainfo.xml" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>${APP_ID}</id>
  <name>Fulcrum</name>
  <summary>Organisational Decision Architecture Sandbox</summary>
  <metadata_license>MIT</metadata_license>
  <project_license>GPL-3.0-only AND LGPL-3.0-only</project_license>
  <developer_name>Oliver Ernster</developer_name>
  <launchable type="desktop-id">${APP_ID}.desktop</launchable>
  <description>
    <p>Fulcrum turns organisational structure into a scored, playable model. Each
    position is a set of teams, dependencies and authority boundaries that a
    deterministic structural model rates from 0 to 100. Structural moves such as
    delegating authority, stabilising interfaces and collapsing boundaries
    transform the score, so you can learn the decision architecture by playing it
    or model your own organisation and export an improvement plan.</p>
  </description>
  <content_rating type="oars-1.1"/>
  <releases>
    <release version="${APP_VERSION}" date="$(date +%Y-%m-%d)"/>
  </releases>
  <url type="homepage">https://oernster.github.io/fulcrum/</url>
</component>
XML

echo "  Packaging helpers ready."

# Manifest
section "Writing manifest ${MANIFEST}"

cat > "${MANIFEST}" <<YAML
app-id: ${APP_ID}
runtime: ${RUNTIME}
runtime-version: "${RUNTIME_VERSION}"
sdk: ${SDK}

command: fulcrum

build-options:
  strip: true
  no-debuginfo: true

finish-args:
  - --share=ipc
  - --socket=fallback-x11
  - --socket=wayland
  - --device=dri
  # Fulcrum stores saved games under ~/Fulcrum/saves and reads/writes user-chosen
  # JSON for org import and plan export/edit, so it needs home access. It uses no
  # network at runtime, so no network permission is granted.
  - --filesystem=home

modules:

  # Python dependencies (local wheels only, fully offline)
  - name: python-deps
    buildsystem: simple
    build-commands:
      - python3 -m ensurepip --upgrade --default-pip
      - pip3 install --no-cache-dir --no-index --find-links wheels --prefix=/app
          -r requirements.txt
    sources:
      - type: dir
        path: .flatpak-wheels
        dest: wheels
      - type: file
        path: requirements.txt

  # Fulcrum application source plus its runtime assets
  - name: fulcrum
    buildsystem: simple
    build-commands:
      - mkdir -p /app/share/${SHARE_DIR}
      - cp main.py VERSION LICENSE LICENSE-GPL-3.0.txt LICENSE-LGPL-3.0.txt /app/share/${SHARE_DIR}/
      - cp -r fulcrum /app/share/${SHARE_DIR}/
      # Book covers shown by Help > Book background, resolved at assets/books.
      - cp -r assets /app/share/${SHARE_DIR}/
      # Loose assets the resource resolver looks for beside main.py: the window
      # and About icon, plus the amber spinbox arrows used by the theme.
      - cp fulcrum.ico fulcrum.png fulcrum_256.png spin_up.png spin_down.png /app/share/${SHARE_DIR}/
      - install -Dm644 fulcrum_16.png  /app/share/icons/hicolor/16x16/apps/${APP_ID}.png
      - install -Dm644 fulcrum_32.png  /app/share/icons/hicolor/32x32/apps/${APP_ID}.png
      - install -Dm644 fulcrum_48.png  /app/share/icons/hicolor/48x48/apps/${APP_ID}.png
      - install -Dm644 fulcrum_64.png  /app/share/icons/hicolor/64x64/apps/${APP_ID}.png
      - install -Dm644 fulcrum_128.png /app/share/icons/hicolor/128x128/apps/${APP_ID}.png
      - install -Dm644 fulcrum_256.png /app/share/icons/hicolor/256x256/apps/${APP_ID}.png
      - install -Dm644 fulcrum_512.png /app/share/icons/hicolor/512x512/apps/${APP_ID}.png
      - install -Dm755 packaging/fulcrum-launcher.sh /app/bin/fulcrum
      - install -Dm644 packaging/${APP_ID}.desktop /app/share/applications/${APP_ID}.desktop
      - install -Dm644 packaging/${APP_ID}.metainfo.xml /app/share/metainfo/${APP_ID}.metainfo.xml
      # Dual licence: the model is GPL-3.0 and the user interface is LGPL-3.0.
      - install -Dm644 LICENSE /app/share/licenses/${APP_ID}/LICENSE
      - install -Dm644 LICENSE-GPL-3.0.txt /app/share/licenses/${APP_ID}/LICENSE-GPL-3.0.txt
      - install -Dm644 LICENSE-LGPL-3.0.txt /app/share/licenses/${APP_ID}/LICENSE-LGPL-3.0.txt
    sources:
      - type: file
        path: main.py
      - type: file
        path: VERSION
      - type: file
        path: LICENSE
      - type: file
        path: LICENSE-GPL-3.0.txt
      - type: file
        path: LICENSE-LGPL-3.0.txt
      - type: file
        path: fulcrum.ico
      - type: file
        path: fulcrum.png
      - type: file
        path: fulcrum_16.png
      - type: file
        path: fulcrum_32.png
      - type: file
        path: fulcrum_48.png
      - type: file
        path: fulcrum_64.png
      - type: file
        path: fulcrum_128.png
      - type: file
        path: fulcrum_256.png
      - type: file
        path: fulcrum_512.png
      - type: file
        path: spin_up.png
      - type: file
        path: spin_down.png
      - type: dir
        path: fulcrum
        dest: fulcrum
      - type: dir
        path: assets
        dest: assets
      - type: dir
        path: packaging
        dest: packaging
YAML

echo "  Manifest written."

# Build
section "Building Flatpak"
rm -rf "${BUILD_DIR}" "${REPO_DIR}"

flatpak-builder \
    --user \
    --install-deps-from=flathub \
    --install \
    --force-clean \
    --repo="${REPO_DIR}" \
    "${BUILD_DIR}" \
    "${MANIFEST}"

# Bundle (on by default; skip with --no-bundle)
if [[ $MAKE_BUNDLE -eq 1 ]]; then
    section "Bundling to ${BUNDLE}"
    echo "  The spinner shows how much of ${BUNDLE} has been written."
    echo
    rm -f "${BUNDLE}"
    run_with_spinner "Writing ${BUNDLE}" --watch "${BUNDLE}" -- \
        flatpak build-bundle "${REPO_DIR}" "${BUNDLE}" "${APP_ID}"
    echo
    echo "${bold}Bundle: ${BUNDLE}  ($(du -sh "${BUNDLE}" | cut -f1))${reset}"
    echo
    echo "Install on another machine:"
    echo "  1. Copy ${BUNDLE} to the target machine"
    echo "  2. flatpak install --user ${BUNDLE}"
    echo "  3. flatpak run ${APP_ID}"
fi

echo
echo "${bold}Build complete.${reset}"
echo
echo "The app is already installed locally. To manage it:"
echo
echo "  Run:        flatpak run ${APP_ID}"
echo "  Uninstall:  flatpak uninstall --user ${APP_ID}"
echo
if [[ $MAKE_BUNDLE -ne 1 ]]; then
    echo "Bundle skipped (--no-bundle). Run without it to produce ${BUNDLE}."
    echo
fi
