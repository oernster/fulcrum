"""The installer window: a themed, state-aware lifecycle screen.

One window, whose caption and visible actions follow the install state
detected at construction: a fresh machine sees Install, an existing one
sees Upgrade, Reinstall or Reinstall (older) alongside Repair and
Uninstall. Every action is guarded by a check that the application is not
running, because replacing a running executable is how an install ends up
half applied.

British spelling is used in comments. No em dashes appear anywhere.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import installer_bundle as bundle
import installer_lifecycle as lifecycle
import installer_logic as logic
import installer_ops as ops
import installer_theme as theme
from installer_widgets import (
    AppRunningDialog,
    LicenceDialog,
    NeutralStart,
    UninstallDialog,
)

APP_DISPLAY_NAME = logic.APP_DISPLAY_NAME
AppState = logic.AppState

# The app takes a few seconds to show its window; the installer stays open
# until it appears (or this passes) and fronts it while the installer still
# owns the foreground, since a window arriving after the installer has gone
# is denied focus by Windows and only flashes on the taskbar.
_FOREGROUND_WAIT_S = 15.0
_FOREGROUND_POLL_MS = 200


class InstallerWindow(QWidget):
    """The installer window: a themed, state-aware lifecycle screen."""

    def __init__(self) -> None:
        super().__init__()
        self._state = lifecycle.detect_state()
        self.setWindowTitle(theme.WINDOW_TITLE)
        self.setWindowIcon(bundle.app_icon())
        self.resize(theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT)
        self.setStyleSheet(theme.STYLESHEET)
        self._desktop = QCheckBox("Create a desktop shortcut")
        self._start_menu = QCheckBox("Create a Start Menu shortcut")
        self._launch_on_finish = QCheckBox(f"Launch {APP_DISPLAY_NAME} when finished")
        self._autostart = QCheckBox(
            f"Start {APP_DISPLAY_NAME} when I sign in to Windows"
        )
        self._status = QLabel("")
        self._status.setObjectName("StatusLine")
        self._status.setWordWrap(True)
        self._primary = QPushButton(lifecycle.primary_label(self._state))
        self._primary.setObjectName("PrimaryAction")
        self._repair = QPushButton("Repair")
        self._repair.setObjectName("SecondaryAction")
        self._uninstall = QPushButton("Uninstall")
        self._uninstall.setObjectName("DangerAction")
        self._shown = False
        # A 0x0 focus sink: launch is neutral, exactly like the app's main
        # window, so nothing wears a ring until the keyboard or the mouse
        # asks for it; the first Tab enters the ring at the first control.
        self._start = NeutralStart(self)
        self._build_ui()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._shown:
            self._shown = True
            self._start.setFocus()

    def keyPressEvent(self, event) -> None:
        # Enter activates the focused control exactly as Space does; a plain
        # QWidget window has no dialog default-button mechanism, so buttons
        # and checkboxes would otherwise ignore it.
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            target = self.focusWidget()
            if isinstance(target, QAbstractButton) and target.isEnabled():
                target.click()
                return
        super().keyPressEvent(event)

    # ----------------------------------------------------------------- layout

    def _build_ui(self) -> None:
        """Assemble the themed installer layout in one top-to-bottom column."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            theme.MARGIN_SIDE, theme.MARGIN_TOP, theme.MARGIN_SIDE, theme.MARGIN_BOTTOM
        )
        layout.setSpacing(theme.SECTION_SPACING)

        layout.addLayout(self._build_header())

        subtitle = QLabel(self._subtitle_text())
        subtitle.setObjectName("SubTitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(subtitle)

        tagline = QLabel(logic.APP_TAGLINE)
        tagline.setObjectName("Tagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        tagline.setWordWrap(True)
        layout.addWidget(tagline)

        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(theme.DIVIDER_PX)
        layout.addWidget(divider)

        path_label = QLabel(f"Install location: {ops.install_target()}")
        path_label.setObjectName("InstallPath")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        self._desktop.setChecked(True)
        layout.addWidget(self._desktop)
        self._start_menu.setChecked(True)
        layout.addWidget(self._start_menu)
        self._launch_on_finish.setChecked(True)
        layout.addWidget(self._launch_on_finish)
        layout.addWidget(self._autostart)
        layout.addWidget(self._status)

        layout.addStretch()
        layout.addLayout(self._build_buttons())

    def _build_header(self) -> QHBoxLayout:
        """Build the header row: icon, title and version, plus licence buttons."""
        header = QHBoxLayout()
        header.setSpacing(theme.HEADER_SPACING)

        icon = bundle.app_icon()
        if not icon.isNull():
            badge = QLabel()
            badge.setPixmap(icon.pixmap(QSize(theme.ICON_PX, theme.ICON_PX)))
            header.addWidget(badge)

        title = QLabel(f"{APP_DISPLAY_NAME} Setup")
        title.setObjectName("HeaderTitle")
        header.addWidget(title)

        version = bundle.app_version()
        if version:
            version_label = QLabel(f"v{version}")
            version_label.setObjectName("HeaderVersion")
            version_label.setAlignment(
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft
            )
            header.addWidget(version_label)

        header.addStretch()

        installer_licence_button = QPushButton("Installer notice")
        installer_licence_button.setObjectName("LicenceButton")
        installer_licence_button.clicked.connect(self._on_show_installer_licence)
        header.addWidget(installer_licence_button)

        model_licence_button = QPushButton("Model licence (GPL-3.0)")
        model_licence_button.setObjectName("LicenceButton")
        model_licence_button.clicked.connect(self._on_show_model_licence)
        header.addWidget(model_licence_button)

        ui_licence_button = QPushButton("UI licence (LGPL-3.0)")
        ui_licence_button.setObjectName("LicenceButton")
        ui_licence_button.clicked.connect(self._on_show_ui_licence)
        header.addWidget(ui_licence_button)
        return header

    def _build_buttons(self) -> QHBoxLayout:
        """Build the action row: primary, Repair, Uninstall and Close."""
        self._primary.clicked.connect(self._on_primary)
        self._repair.clicked.connect(self._on_repair)
        self._uninstall.clicked.connect(self._on_uninstall)
        close_button = QPushButton("Close")
        close_button.setObjectName("SecondaryAction")
        close_button.clicked.connect(self.close)

        installed = self._state != AppState.NOT_INSTALLED
        self._repair.setVisible(installed)
        self._uninstall.setVisible(installed)

        buttons = QHBoxLayout()
        buttons.setSpacing(theme.BUTTON_GAP)
        buttons.addWidget(self._uninstall)
        buttons.addStretch()
        buttons.addWidget(self._repair)
        buttons.addWidget(self._primary)
        buttons.addWidget(close_button)
        return buttons

    def _subtitle_text(self) -> str:
        """Return a subtitle reflecting whether this is a fresh install."""
        if self._state == AppState.NOT_INSTALLED:
            return f"Welcome to the {APP_DISPLAY_NAME} installer"
        return f"{APP_DISPLAY_NAME} is already installed"

    # ---------------------------------------------------------------- actions

    def _on_show_model_licence(self) -> None:
        """Open the model (GPL-3.0) licence in a themed dialog."""
        LicenceDialog(
            bundle.licence_text(logic.MODEL_LICENSE_FILE_NAME),
            f"{APP_DISPLAY_NAME} Model Licence (GPL-3.0)",
            self,
        ).exec()

    def _on_show_ui_licence(self) -> None:
        """Open the UI (LGPL-3.0) licence in a themed dialog."""
        LicenceDialog(
            bundle.licence_text(logic.UI_LICENSE_FILE_NAME),
            f"{APP_DISPLAY_NAME} UI Licence (LGPL-3.0)",
            self,
        ).exec()

    def _on_show_installer_licence(self) -> None:
        """Open the installer-wrapper licence notice in a themed dialog."""
        LicenceDialog(
            bundle.installer_licence_text(),
            f"{APP_DISPLAY_NAME} Installer Notice",
            self,
        ).exec()

    def _guard_not_running(self, action: str) -> bool:
        """True when the app is not running; otherwise ask the user to
        close it, offering Retry until it is gone or they cancel."""
        if not ops.is_app_running():
            return True
        if AppRunningDialog(action, self).exec() == QDialog.DialogCode.Accepted:
            return True
        self._status.setText(
            f"{APP_DISPLAY_NAME} is still running, so the {action} was cancelled."
        )
        return False

    def _on_primary(self) -> None:
        """Install, upgrade or reinstall, then optionally launch the app."""
        if not self._guard_not_running("installation"):
            return
        self._set_busy("Installing...")
        try:
            exe_path = lifecycle.install(
                ops.install_target(),
                desktop=self._desktop.isChecked(),
                start_menu=self._start_menu.isChecked(),
                autostart=self._autostart.isChecked(),
            )
        except Exception as error:  # noqa: BLE001 - surfaced as a status message
            self._finish_error(f"Installation failed: {error}")
            return
        self._status.setText(f"Installed to {exe_path.parent}.")
        if self._launch_on_finish.isChecked():
            self._launch_and_front(exe_path)
            return
        self._refresh_after_change()

    def _launch_and_front(self, exe_path: Path) -> None:
        """Launch the app, wait for its window, front it, then close."""
        process = ops.launch(exe_path)
        if process is None:
            self.close()
            return
        self._set_busy(f"Launching {APP_DISPLAY_NAME}...")
        self._front_pid = process.pid
        self._front_deadline = time.monotonic() + _FOREGROUND_WAIT_S
        self._front_timer = QTimer(self)
        self._front_timer.timeout.connect(self._front_launched_app)
        self._front_timer.start(_FOREGROUND_POLL_MS)

    def _front_launched_app(self) -> None:
        fronted = ops.bring_process_window_to_front(self._front_pid)
        if fronted or time.monotonic() > self._front_deadline:
            self._front_timer.stop()
            self.close()

    def _on_repair(self) -> None:
        """Re-deploy the application files over the existing install."""
        if not self._guard_not_running("repair"):
            return
        location = ops.installed_location() or ops.install_target()
        self._set_busy("Repairing...")
        try:
            lifecycle.repair(location)
        except Exception as error:  # noqa: BLE001 - surfaced as a status message
            self._finish_error(f"Repair failed: {error}")
            return
        self._status.setText("Repair complete.")
        self._refresh_after_change()

    def _on_uninstall(self) -> None:
        """Confirm, then remove the application, shortcuts and registration."""
        if not self._guard_not_running("uninstall"):
            return
        dialog = UninstallDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._set_busy("Uninstalling...")
        try:
            lifecycle.uninstall(remove_settings=dialog.remove_settings())
        except Exception as error:  # noqa: BLE001 - surfaced as a status message
            self._finish_error(f"Uninstall failed: {error}")
            return
        self._status.setText(f"{APP_DISPLAY_NAME} has been uninstalled.")
        self._state = AppState.NOT_INSTALLED
        self._primary.setText(lifecycle.primary_label(self._state))
        self._repair.setVisible(False)
        self._uninstall.setVisible(False)
        self._primary.setEnabled(True)

    def _set_busy(self, message: str) -> None:
        """Show a status message and disable the action buttons during work."""
        self._status.setText(message)
        self._primary.setEnabled(False)
        self._repair.setEnabled(False)
        self._uninstall.setEnabled(False)
        QApplication.processEvents()

    def _finish_error(self, message: str) -> None:
        """Show an error and restore the buttons to their accepted state."""
        self._status.setText(message)
        self._primary.setEnabled(True)
        self._repair.setEnabled(True)
        self._uninstall.setEnabled(True)

    def _refresh_after_change(self) -> None:
        """Re-detect state after an install or repair and relabel the buttons."""
        self._state = lifecycle.detect_state()
        self._primary.setText(lifecycle.primary_label(self._state))
        installed = self._state != AppState.NOT_INSTALLED
        self._repair.setVisible(installed)
        self._uninstall.setVisible(installed)
        self._uninstall.setEnabled(True)
        self._primary.setEnabled(True)
        self._repair.setEnabled(True)
