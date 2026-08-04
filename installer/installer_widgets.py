"""The installer's shared widgets: the self-reading surface and the dialogs.

The auto-scroller is a standalone copy of the application's, so a licence
opened in the installer reads itself at the same pace it does in the app.
The dialogs are the two the lifecycle needs: the ask to close a running
application, and the uninstall confirmation.

British spelling is used in comments. No em dashes appear anywhere.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import installer_bundle as bundle
import installer_logic as logic
import installer_ops as ops
import installer_theme as theme

APP_DISPLAY_NAME = logic.APP_DISPLAY_NAME


def licence_view_width(view: QTextEdit, text: str) -> int:
    """Return the pixel width that shows the widest licence line in full."""
    view.ensurePolished()
    metrics = view.fontMetrics()
    lines = text.splitlines() or [text]
    widest = max(metrics.horizontalAdvance(line) for line in lines)
    doc_margin = round(view.document().documentMargin())
    scrollbar = view.verticalScrollBar().sizeHint().width()
    chrome = theme.SIDES * (doc_margin + theme.TEXT_PADDING_PX + theme.BORDER_PX)
    return widest + scrollbar + chrome + theme.WIDTH_SAFETY_PX


class AutoScroller(QObject):
    """Cycles a scrollable widget: down slowly, pause, rewind fast, repeat.

    A standalone copy of the application's scroller (the installer imports
    nothing from the fulcrum package), carrying the same app-wide pace: the
    cycle holds still for a moment when the surface opens, reads down,
    holds at the bottom, rewinds fast, holds at the top and repeats. Any
    manual reading input (wheel, click, key, scrollbar or focus entering
    the surface) suspends it briefly; it resumes from wherever the reader
    left it, never switching off. The widget becomes the scroller's Qt
    parent, so their lifetimes match.
    The installer has no UI-scale helper, so the descent step is a
    plain pixel with the same 1px floor the app applies after scaling.
    """

    _TICK_MS = 40
    _DOWN_STEP_PX = 1
    # The descent advances one step every second tick: the app's standard
    # reading pace, gentle enough for dense content on every surface.
    _DOWN_TICKS_PER_STEP = 2
    # The rewind is a reposition, not a reading pass, so it travels fast.
    _UP_STEP_PX = 15
    # Hold at the end long enough to finish reading the tail before the
    # rewind takes it away.
    _BOTTOM_PAUSE_MS = 5000
    _TOP_PAUSE_MS = 2000
    # A fresh surface holds still before its first descent, so the reader
    # orients before anything starts to move.
    _START_PAUSE_MS = 5000
    # Stillness required after a manual scroll before the cycle resumes.
    _RESUME_AFTER_MS = 2500

    _DOWN = "down"
    _UP = "up"
    _PAUSE_TOP = "pause_top"
    _PAUSE_BOTTOM = "pause_bottom"
    _MANUAL = "manual"
    _WAITING = (_PAUSE_TOP, _PAUSE_BOTTOM, _MANUAL)
    _MANUAL_EVENTS = (
        QEvent.Type.Wheel,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.KeyPress,
    )

    def __init__(self, area) -> None:
        super().__init__(area)
        self._area = area
        self._bar = area.verticalScrollBar()
        self._down_countdown = self._DOWN_TICKS_PER_STEP
        # Open holding still, then the first descent begins; the guard in
        # the tick means the wait only counts down once content overflows.
        self._phase = self._PAUSE_TOP
        self._wait_ms = self._START_PAUSE_MS
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self._TICK_MS)
        # The viewport sees the wheel and clicks, the widget sees the keys.
        area.installEventFilter(self)
        area.viewport().installEventFilter(self)
        self._bar.sliderPressed.connect(self.suspend)
        self._bar.sliderReleased.connect(self.suspend)
        self._bar.sliderMoved.connect(self._on_slider_moved)
        # Keyboard focus entering the surface or a child is reading by hand
        # too; a child never sees this filter, so watch the application's
        # focus instead.
        QApplication.instance().focusChanged.connect(self._on_focus_changed)

    def suspend(self) -> None:
        """Hand the content to the reader and start counting down to resume."""
        self._phase = self._MANUAL
        self._wait_ms = self._RESUME_AFTER_MS

    def _on_slider_moved(self, _value: int) -> None:
        """Dragging the scrollbar counts as reading by hand."""
        self.suspend()

    def _on_focus_changed(self, _old, new) -> None:
        if isinstance(new, QWidget) and (
            new is self._area or self._area.isAncestorOf(new)
        ):
            self.suspend()

    def eventFilter(self, obj, event) -> bool:
        if event.type() in self._MANUAL_EVENTS:
            self.suspend()
        return False

    def _frozen_under_modal(self) -> bool:
        """Whether a modal above this surface should freeze the cycle.

        Two surfaces reading at once compete for the eye, so while a modal
        dialog is up only ITS surfaces read; anything beneath freezes in
        place (no wait is consumed) and resumes exactly where it was when
        the modal closes.
        """
        modal = QApplication.activeModalWidget()
        if modal is None:
            return False
        return not (modal is self._area.window() or modal.isAncestorOf(self._area))

    def _tick(self) -> None:
        if self._frozen_under_modal():
            return
        maximum = self._bar.maximum()
        if maximum <= 0:
            return
        if self._phase in self._WAITING:
            self._wait_ms -= self._TICK_MS
            if self._wait_ms <= 0:
                self._phase = self._resumed_phase(maximum)
            return
        if self._phase == self._DOWN:
            self._down_countdown -= 1
            if self._down_countdown > 0:
                return
            self._down_countdown = self._DOWN_TICKS_PER_STEP
            value = self._bar.value() + max(1, self._DOWN_STEP_PX)
            if value >= maximum:
                self._bar.setValue(maximum)
                self._phase = self._PAUSE_BOTTOM
                self._wait_ms = self._BOTTOM_PAUSE_MS
            else:
                self._bar.setValue(value)
            return
        value = self._bar.value() - max(1, self._UP_STEP_PX)
        if value <= 0:
            self._bar.setValue(0)
            self._phase = self._PAUSE_TOP
            self._wait_ms = self._TOP_PAUSE_MS
        else:
            self._bar.setValue(value)

    def _resumed_phase(self, maximum: int) -> str:
        """The direction to travel once a wait ends.

        After the bottom hold the cycle rewinds. After a manual scroll it
        reads onward from wherever the reader stopped, unless they are
        already at the end, in which case rewinding is the only way on.
        """
        if self._phase == self._PAUSE_BOTTOM:
            return self._UP
        if self._phase == self._MANUAL and self._bar.value() >= maximum:
            return self._UP
        return self._DOWN


class NeutralStart(QWidget):
    """A 0x0 focus sink so the dialog opens with nothing ringed.

    Without it Qt hands the dialog's first focus to the licence view, which
    would suspend the auto-scroll the moment the dialog opens. It leaves
    the tab chain as soon as focus moves on, so the cycle that follows
    holds only real controls.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(0, 0)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class LicenceDialog(QDialog):
    """A themed, scrollable view of a licence text that reads itself.

    The licence descends at the app's standard reading pace from the moment
    the dialog opens; any manual scroll or focus into the view suspends the
    cycle briefly and it resumes in place.
    """

    def __init__(
        self,
        licence_text: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowIcon(bundle.app_icon())
        self.setStyleSheet(theme.STYLESHEET)

        layout = QVBoxLayout(self)
        margin = theme.DIALOG_MARGIN
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(theme.BUTTON_GAP)

        # First in the tab chain, so opening the dialog focuses the sink
        # rather than the view and the descent starts unsuspended.
        self._start = NeutralStart(self)
        layout.addWidget(self._start)
        self._started = False

        view = QTextEdit()
        view.setObjectName("LicenceView")
        view.setReadOnly(True)
        view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        view.setPlainText(licence_text)
        layout.addWidget(view)
        AutoScroller(view)

        view_width = licence_view_width(view, licence_text)
        view.setMinimumWidth(view_width)
        self.resize(view_width + theme.SIDES * margin, theme.LICENCE_DIALOG_HEIGHT)

        close = QPushButton("Close")
        close.setObjectName("SecondaryAction")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        layout.addLayout(row)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._started:
            self._started = True
            self._start.setFocus()


class AppRunningDialog(QDialog):
    """A themed ask to close the running app before setup continues.

    Retry re-checks the task list and accepts once the app is gone;
    Cancel abandons the action. A premature retry gets an immediate
    still-running notice rather than a silent no-op.
    """

    def __init__(self, action: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{APP_DISPLAY_NAME} Setup")
        self.setWindowIcon(bundle.app_icon())
        self.setStyleSheet(theme.STYLESHEET)

        layout = QVBoxLayout(self)
        margin = theme.DIALOG_MARGIN
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(theme.BUTTON_GAP)

        self._start = NeutralStart(self)
        layout.addWidget(self._start)
        self._started = False

        message = QLabel(
            f"{APP_DISPLAY_NAME} is currently running. Close it, then choose "
            f"Retry to continue with the {action}."
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        self._notice = QLabel("")
        self._notice.setObjectName("StatusLine")
        self._notice.setWordWrap(True)
        layout.addWidget(self._notice)

        retry = QPushButton("Retry")
        retry.setObjectName("PrimaryAction")
        retry.clicked.connect(self._on_retry)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("SecondaryAction")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(retry)
        layout.addLayout(row)

    def _on_retry(self) -> None:
        if ops.is_app_running():
            self._notice.setText(
                f"{APP_DISPLAY_NAME} is still running. Close it first."
            )
            return
        self.accept()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._started:
            self._started = True
            self._start.setFocus()


class UninstallDialog(QDialog):
    """A small themed uninstall confirmation, with a remove-settings option."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Uninstall {APP_DISPLAY_NAME}")
        self.setWindowIcon(bundle.app_icon())
        self.setStyleSheet(theme.STYLESHEET)

        layout = QVBoxLayout(self)
        margin = theme.DIALOG_MARGIN
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(theme.BUTTON_GAP)

        message = QLabel(
            f"Remove {APP_DISPLAY_NAME} and its shortcuts from this PC? Your "
            "saved games are kept unless you tick the box below."
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        self._remove_settings = QCheckBox(
            f"Also remove my {APP_DISPLAY_NAME} settings and saved games"
        )
        layout.addWidget(self._remove_settings)

        confirm = QPushButton("Uninstall")
        confirm.setObjectName("DangerAction")
        confirm.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("SecondaryAction")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(confirm)
        layout.addLayout(row)

    def remove_settings(self) -> bool:
        """Return whether the user asked to also remove their settings."""
        return self._remove_settings.isChecked()
