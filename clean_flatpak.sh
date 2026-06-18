#!/usr/bin/env bash
# clean_flatpak.sh - Uninstall and purge the Fulcrum Flatpak
#
# Scoped to flatpak artefacts only. It deliberately does NOT touch the Nuitka
# outputs (installer/payload, dist-installer) produced by buildexe.py /
# buildinstaller.py, nor the macOS outputs from builddmg.py, so the build paths
# stay independent.
set -euo pipefail

APP_ID="uk.codecrafter.Fulcrum"

bold=$(tput bold 2>/dev/null || true)
reset=$(tput sgr0 2>/dev/null || true)
section() { echo; echo "${bold}=== $* ===${reset}"; }

section "Uninstalling ${APP_ID}"
if flatpak list --user | grep -q "${APP_ID}"; then
    flatpak uninstall --user -y "${APP_ID}"
    echo "  Uninstalled."
else
    echo "  Not installed, skipping."
fi

section "Removing flatpak build artefacts"
rm -f fulcrum.flatpak
rm -rf .flatpak-build .flatpak-repo .flatpak-builder .flatpak-wheels
rm -f "${APP_ID}.yml"
rm -rf packaging/
echo "  Done."

echo
echo "${bold}Purge complete.${reset}"
