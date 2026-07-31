"""Honour a native close request aimed at a modally blocked main window.

Qt discards a spontaneous close event sent to a window that a modal dialog
is blocking: the event is dropped before any widget or application event
filter can observe it, so quitting from the Windows taskbar while a dialog
is open would otherwise do nothing at all. This guard watches the native
message stream for WM_CLOSE aimed at the main window while a modal is up,
dismisses the open modal dialogs and then runs the window's normal close
flow (autosave included). Windows-only: install_close_guard is a no-op on
other platforms.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtWidgets import QApplication, QWidget

_WM_CLOSE = 0x0010
_WINDOWS_MESSAGE_TYPE = b"windows_generic_MSG"
# A ceiling on stacked modal dialogs: a reject that refuses to take effect
# can then never spin the dismissal loop forever.
_MAX_STACKED_MODALS = 8

if sys.platform == "win32":
    from ctypes import wintypes as _wintypes


class _WindowsCloseGuard(QAbstractNativeEventFilter):
    """Native filter delivering WM_CLOSE past Qt's modal-block discard."""

    def __init__(self, window: QWidget) -> None:
        super().__init__()
        self._window = window

    def nativeEventFilter(self, event_type, message):
        if event_type != _WINDOWS_MESSAGE_TYPE:
            return False, 0
        msg = _wintypes.MSG.from_address(int(message))
        if msg.message != _WM_CLOSE:
            return False, 0
        if msg.hWnd != int(self._window.winId()):
            return False, 0
        if QApplication.activeModalWidget() is None:
            # Nothing blocks the window, so the ordinary close path works.
            return False, 0
        for _ in range(_MAX_STACKED_MODALS):
            modal = QApplication.activeModalWidget()
            if modal is None:
                break
            modal.reject()
        self._window.close()
        return True, 0


def install_close_guard(window: QWidget) -> QAbstractNativeEventFilter | None:
    """Attach the guard for the window; the caller keeps the returned filter."""
    if sys.platform != "win32":
        return None
    guard = _WindowsCloseGuard(window)
    QApplication.instance().installNativeEventFilter(guard)
    return guard
