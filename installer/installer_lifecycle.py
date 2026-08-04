"""The install, repair and uninstall sequences, with no Qt.

Each function here is a composition: it asks installer_logic what should
happen and installer_ops to make it happen, in the order that leaves a
working machine at every point. The order matters. Files are deployed
before the uninstaller is registered, so a registration always points at
something that exists, and the install directory is removed last on
uninstall, so a failure part way through still leaves the app findable.

British spelling is used in comments. No em dashes appear anywhere.
"""

from __future__ import annotations

from pathlib import Path

import installer_bundle as bundle
import installer_logic as logic
import installer_ops as ops


def _deploy(target: Path) -> Path:
    """Extract the bundled application archive to ``target``; return the exe."""
    return logic.deploy_files(logic.payload_archive(bundle.bundle_root()), target)


def _register(install_dir: Path, uninstaller: Path) -> None:
    """Write the HKCU Apps and features registration for a deployed install."""
    ops.write_uninstall_entry(
        logic.uninstall_entry_values(
            install_dir,
            uninstaller,
            bundle.app_version() or logic.FALLBACK_VERSION,
            logic.dir_size_kb(install_dir),
        )
    )


def install(target: Path, *, desktop: bool, start_menu: bool, autostart: bool) -> Path:
    """Run the full install/upgrade/reinstall: files, registry and shortcuts."""
    exe_path = _deploy(target)
    _register(target, ops.copy_uninstaller(target))
    ops.apply_shortcuts(exe_path, desktop=desktop, start_menu=start_menu)
    ops.set_autostart(autostart, exe_path)
    return exe_path


def repair(install_dir: Path) -> Path:
    """Re-deploy the application files over an existing install, then register.

    Without a per-file manifest the safe, simple repair is a full re-copy of the
    bundled files: it restores anything missing or altered. User settings live
    outside the install directory, so they are untouched.
    """
    exe_path = _deploy(install_dir)
    _register(install_dir, ops.copy_uninstaller(install_dir))
    ops.apply_shortcuts(exe_path, desktop=True, start_menu=True)
    return exe_path


def uninstall(*, remove_settings: bool) -> None:
    """Remove shortcuts, registry, autostart, user state and the install dir."""
    install_dir = ops.installed_location() or ops.install_target()
    ops.remove_shortcut(ops.desktop_link())
    ops.remove_shortcut(ops.start_menu_link())
    ops.remove_autostart()
    ops.delete_uninstall_entry()
    ops.delete_toast_identity()
    ops.remove_state(remove_settings)
    ops.remove_install_dir(install_dir)


def detect_state() -> str:
    """Classify the current install against the bundled version."""
    return logic.detect_state(
        ops.installed_version(), ops.installed_location(), bundle.app_version()
    )


def primary_label(state: str) -> str:
    """Return the primary button caption for an install state."""
    return logic.primary_label(state, bundle.app_version())
