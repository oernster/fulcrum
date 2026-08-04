#!/usr/bin/env python3
"""Fulcrum installer: the entry point.

A self-contained PySide6 installer compiled into a single executable by
buildinstaller.py. It carries the built application bundle and the LICENCE as an
embedded payload (staged under ``payload/`` by the build tooling) and provides
the full lifecycle the author's other installers offer:

- Install, upgrade, reinstall and repair the per-user application.
- Register the app in Windows "Apps & features" (the HKCU Uninstall key), so it
  appears as an installed program with a working Uninstall action.
- Uninstall (also runnable headlessly via ``--uninstall``, which is how the
  registered UninstallString re-invokes a copy of this installer).
- Optional desktop and Start Menu shortcuts, and optional launch at sign-in.

It never needs administrator rights: it deploys to
``%LOCALAPPDATA%\\Programs\\Fulcrum`` and registers under HKCU. It is
deliberately standalone (it imports nothing from the ``fulcrum`` package) and
dependency-light: process detection uses ``tasklist``, version comparison is a
plain tuple compare and shortcuts are written through the Windows scripting
host, so the onefile build pulls in nothing beyond PySide6 and the stdlib.

The installer is a second application, and it is layered like one:

- ``installer_logic`` decides (pure, and covered by the test suite at 100%).
- ``installer_ops`` acts (registry, processes, shortcuts, shell-outs).
- ``installer_lifecycle`` composes the two into install, repair and uninstall.
- ``installer_bundle`` reads the payload beside this binary.
- ``installer_theme``, ``installer_widgets`` and ``installer_window`` are the
  Qt surface, outside the coverage gate exactly as the application's UI is.

British spelling is used in comments. No em dashes appear anywhere.
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication, QDialog

import installer_bundle as bundle
import installer_lifecycle as lifecycle
import installer_logic as logic
import installer_ops as ops
import installer_theme as theme
from installer_widgets import AppRunningDialog, UninstallDialog
from installer_window import InstallerWindow

APP_DISPLAY_NAME = logic.APP_DISPLAY_NAME


def _new_application(name: str) -> QApplication:
    """Create the QApplication with the installer's identity and style."""
    app = QApplication(sys.argv)
    # Pin Fusion: the native windows11 style paints over stylesheet borders.
    app.setStyle("fusion")
    app.setApplicationName(name)
    app.setWindowIcon(bundle.app_icon())
    return app


def _run_uninstall_cli(args: argparse.Namespace) -> int:
    """Run the uninstall flow when invoked as the registered uninstaller."""
    _new_application(f"{APP_DISPLAY_NAME} Setup")
    if args.quiet:
        lifecycle.uninstall(remove_settings=args.remove_settings)
        return 0
    dialog = UninstallDialog()
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return 0
    if ops.is_app_running():
        gate = AppRunningDialog("uninstall")
        if gate.exec() != QDialog.DialogCode.Accepted:
            return 0
    lifecycle.uninstall(remove_settings=dialog.remove_settings())
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse the installer command line (used for the registered uninstaller)."""
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(logic.UNINSTALL_FLAG, dest="uninstall", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--remove-settings", action="store_true")
    return parser.parse_args(argv)


def main() -> int:
    """Run the installer GUI, or the uninstall flow when so invoked."""
    ops.install_crash_logging()
    ops.set_app_user_model_id()
    args = _parse_args(sys.argv[1:])
    if args.uninstall:
        return _run_uninstall_cli(args)

    app = _new_application(theme.WINDOW_TITLE)
    window = InstallerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
