"""Gentle auto-scroll for long content, in the ClearBudget style.

The cycle reads down slowly from the moment the surface opens, holds at the
bottom so the tail can be read, rewinds to the top at a faster pace, holds
briefly and starts over. Manual scrolling (wheel, click, dragging the
scrollbar or the arrow keys) only suspends the cycle: once the reader has
been still for a moment it picks up from wherever they left it, so taking
over by hand never switches the feature off for the rest of the surface's
life. While the pointer hovers the surface the cycle holds still, so a
control inside it never moves away from under the cursor, and focus
entering the surface (keyboard navigation into a list) suspends it too.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication, QWidget

from fulcrum.ui import ui_scale


class AutoScroller(QObject):
    """Cycles a scrollable widget: down slowly, pause, rewind fast, repeat.

    Works on any scroll surface exposing verticalScrollBar() and viewport()
    (a QTextBrowser showing credits or a licence, a QScrollArea of cards or
    move buttons). The widget becomes the scroller's Qt parent, so their
    lifetimes match.
    """

    _TICK_MS = 40
    _DOWN_STEP_PX = 1
    _UP_STEP_PX = 6
    _BOTTOM_PAUSE_MS = 4000
    _TOP_PAUSE_MS = 2000
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
        # Straight into the first descent: nothing is held back on opening.
        self._phase = self._DOWN
        self._wait_ms = 0
        self._hovered = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self._TICK_MS)
        # The viewport sees the wheel and clicks, the widget sees the keys.
        area.installEventFilter(self)
        area.viewport().installEventFilter(self)
        self._bar.sliderPressed.connect(self.suspend)
        self._bar.sliderReleased.connect(self.suspend)
        self._bar.sliderMoved.connect(self._on_slider_moved)
        # Keyboard navigation into a child (a move button taking focus) is
        # reading by hand too; the child never sees this filter, so watch
        # the application's focus instead.
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
        elif event.type() == QEvent.Type.Enter:
            self._hovered = True
        elif event.type() == QEvent.Type.Leave:
            # Resume a moment after the pointer leaves, from where it rests.
            self._hovered = False
            self.suspend()
        return False

    def _tick(self) -> None:
        # A hovered surface holds still, so nothing moves under the cursor.
        if self._hovered:
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
            value = self._bar.value() + max(1, ui_scale.px(self._DOWN_STEP_PX))
            if value >= maximum:
                self._bar.setValue(maximum)
                self._phase = self._PAUSE_BOTTOM
                self._wait_ms = self._BOTTOM_PAUSE_MS
            else:
                self._bar.setValue(value)
            return
        value = self._bar.value() - max(1, ui_scale.px(self._UP_STEP_PX))
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
