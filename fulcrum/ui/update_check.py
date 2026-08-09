"""The update check's UI: triggers, worker thread and the three dialogs.

Threading shape (the house pattern): the worker thread emits ``_result_ready``,
which is connected to a bound method of this controller. The controller lives
on the UI thread, so delivery is a queued connection and the slot (and every
dialog it opens) runs on the UI thread; a signal connected to a bare callable
would run in the worker's thread instead.

The automatic check (a few seconds after launch, then daily) honours the
skipped version and is silent on every non-offer outcome. The manual Help-menu
check ignores the skip and reports every outcome.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QWidget

from fulcrum.application.interfaces import SettingsStore
from fulcrum.application.update_info import UpdateStatus
from fulcrum.application.update_service import UpdateService
from fulcrum.version import APP_NAME

# The launch check waits so it never contends with startup work; the periodic
# re-check covers sessions that stay open for days.
_LAUNCH_DELAY_MS = 3000
_RECHECK_INTERVAL_MS = 24 * 60 * 60 * 1000

_TITLE = "Check for updates"


class UpdateCheckController(QObject):
    """Owns the update check's triggers, worker and dialogs."""

    _result_ready = Signal(object, bool)

    def __init__(
        self,
        window: QWidget,
        service: UpdateService,
        settings: SettingsStore | None,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._service = service
        self._settings = settings
        self._result_ready.connect(self._apply_result)

        QTimer.singleShot(_LAUNCH_DELAY_MS, self.check_automatically)
        self._recheck_timer = QTimer(self)
        self._recheck_timer.setInterval(_RECHECK_INTERVAL_MS)
        self._recheck_timer.timeout.connect(self.check_automatically)
        self._recheck_timer.start()

    def check_automatically(self) -> None:
        """The launch or periodic check: silent on every non-offer outcome."""
        skipped = (
            self._settings.load_skipped_update_version()
            if self._settings is not None
            else None
        )
        self._start_check(skipped, manual=False)

    def check_manually(self) -> None:
        """The Help-menu check: reports every outcome and ignores the skip."""
        self._start_check(None, manual=True)

    def _start_check(self, skipped_version: str | None, manual: bool) -> None:
        def _run() -> None:
            try:
                status = self._service.check(skipped_version)
            except Exception:  # noqa: BLE001 (any error reads as unreachable)
                status = None
            self._result_ready.emit(status, manual)

        threading.Thread(target=_run, daemon=True, name="fulcrum-update-check").start()

    @Slot(object, bool)
    def _apply_result(self, status: UpdateStatus | None, manual: bool) -> None:
        if status is None:
            if manual:
                QMessageBox.warning(
                    self._window,
                    _TITLE,
                    "The update check could not reach GitHub. "
                    "Please try again later.",
                )
            return
        if status.update_available:
            self._offer(status)
            return
        if manual:
            QMessageBox.information(
                self._window, _TITLE, "You are running the latest version."
            )

    def _offer(self, status: UpdateStatus) -> None:
        box = QMessageBox(self._window)
        box.setWindowTitle("Update available")
        box.setText(
            f"{APP_NAME} {status.latest} is available.\n"
            f"You are running {status.current}."
        )
        download = box.addButton("Download", QMessageBox.ButtonRole.AcceptRole)
        skip = box.addButton(
            "Skip This Version", QMessageBox.ButtonRole.DestructiveRole
        )
        box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked is download:
            url = status.download_url or status.page_url
            if url:
                QDesktopServices.openUrl(QUrl(url))
        elif clicked is skip and self._settings is not None:
            self._settings.save_skipped_update_version(status.latest)
