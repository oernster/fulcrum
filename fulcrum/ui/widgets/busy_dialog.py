"""A small modal busy indicator shown while a background task runs."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout

from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog

_MIN_WIDTH = 320
_BUSY_RANGE = 0


class BusyDialog(NeutralDialog):
    """A modal, cancel-less 'working' dialog with a progress bar.

    The bar starts indeterminate; the first set_progress call turns it into
    a real 0..total bar, so a worker that reports its sections shows a bar
    that genuinely fills. Shown without blocking the event loop (via show,
    not exec), so the worker thread keeps running and its finished signal
    is still delivered.
    """

    def __init__(self, message: str, parent=None) -> None:
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
        self._bar.setRange(_BUSY_RANGE, _BUSY_RANGE)
        self._bar.setTextVisible(False)
        layout.addWidget(self._bar)

    def set_progress(self, done: int, total: int) -> None:
        """Advance the bar; the first call makes it determinate."""
        if total > 0:
            self._bar.setMaximum(total)
            self._bar.setValue(done)
