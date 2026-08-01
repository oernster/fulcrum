"""A small modal busy indicator shown while a background task runs."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog

_MIN_WIDTH = 320
_BUSY_RANGE = 0
# A determinate bar needs a non-zero maximum to render empty before the
# first real progress report rescales it.
_EMPTY_MAX = 1


class BusyDialog(NeutralDialog):
    """A modal 'working' dialog with a progress bar and an optional Cancel.

    A worker that reports its sections passes determinate=True: the bar
    starts EMPTY (an indeterminate bar renders as full on some styles, which
    reads as a bar stuck at 100%) and set_progress fills it genuinely. A
    worker with nothing to report keeps the indeterminate animation. Shown
    without blocking the event loop (via show, not exec), so the worker
    thread keeps running and its finished signal is still delivered.

    on_cancel, when given, adds a Cancel button (Escape presses it too):
    clicking asks the worker to stop and the dialog stays up, its button
    reading "Cancelling...", until the worker confirms and the caller
    dismisses it. The user cannot close the dialog directly (close would
    orphan the running worker), so QDialog's own close/reject paths are
    routed to cancellation; the caller closes it through dismiss(), the
    one path allowed to actually hide it.
    """

    def __init__(
        self,
        message: str,
        parent=None,
        determinate: bool = False,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fulcrum")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setMinimumWidth(ui_scale.px(_MIN_WIDTH))
        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setObjectName("Muted")
        layout.addWidget(label)
        self._bar = QProgressBar()
        if determinate:
            self._bar.setRange(_BUSY_RANGE, _EMPTY_MAX)
            self._bar.setValue(_BUSY_RANGE)
        else:
            self._bar.setRange(_BUSY_RANGE, _BUSY_RANGE)
        self._bar.setTextVisible(False)
        layout.addWidget(self._bar)
        self._on_cancel = on_cancel
        self._dismissed = False
        self._cancel_button: QPushButton | None = None
        if on_cancel is not None:
            row = QHBoxLayout()
            self._cancel_button = QPushButton("Cancel")
            self._cancel_button.clicked.connect(self._request_cancel)
            row.addStretch()
            row.addWidget(self._cancel_button)
            layout.addLayout(row)

    def set_progress(self, done: int, total: int) -> None:
        """Advance the bar; the first call makes it determinate."""
        if total > 0:
            self._bar.setMaximum(total)
            self._bar.setValue(done)

    def dismiss(self) -> None:
        """Close the dialog; the worker is finished with it.

        The only path that actually hides the dialog: user-driven close
        and Escape route to cancellation instead, so the callers that
        receive the worker's built or cancelled signal call this.
        """
        self._dismissed = True
        self.close()

    def _request_cancel(self) -> None:
        """Ask the worker to stop, once; the caller dismisses the dialog
        when the worker confirms, so the button dims to show it took."""
        if self._cancel_button is None or not self._cancel_button.isEnabled():
            return
        self._cancel_button.setEnabled(False)
        self._cancel_button.setText("Cancelling...")
        self._on_cancel()

    def closeEvent(self, event) -> None:
        # Only dismiss() may close the dialog: QDialog routes close
        # through reject and ignores it when the dialog stays visible,
        # so an unguarded user close (Alt+F4) is turned into a
        # cancellation request instead of orphaning the worker.
        if self._dismissed:
            event.accept()
            return
        event.ignore()
        self._request_cancel()

    def reject(self) -> None:
        # Escape routes to cancellation when available and is otherwise
        # swallowed: closing the dialog would orphan the running worker.
        self._request_cancel()
