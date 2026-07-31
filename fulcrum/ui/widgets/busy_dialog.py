"""A small modal busy indicator shown while a background task runs."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout

from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog

_MIN_WIDTH = 320
_BUSY_RANGE = 0
# A determinate bar needs a non-zero maximum to render empty before the
# first real progress report rescales it.
_EMPTY_MAX = 1


class BusyDialog(NeutralDialog):
    """A modal, cancel-less 'working' dialog with a progress bar.

    A worker that reports its sections passes determinate=True: the bar
    starts EMPTY (an indeterminate bar renders as full on some styles, which
    reads as a bar stuck at 100%) and set_progress fills it genuinely. A
    worker with nothing to report keeps the indeterminate animation. Shown
    without blocking the event loop (via show, not exec), so the worker
    thread keeps running and its finished signal is still delivered.
    """

    def __init__(self, message: str, parent=None, determinate: bool = False) -> None:
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

    def set_progress(self, done: int, total: int) -> None:
        """Advance the bar; the first call makes it determinate."""
        if total > 0:
            self._bar.setMaximum(total)
            self._bar.setValue(done)
