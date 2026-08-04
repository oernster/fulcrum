"""A reusable keyboard focus ring for modal dialogs.

Tab and Right step forward through the dialog's stops; Shift+Tab and Left
step back; both wrap. A stop is either one widget or a group holder whose
focusable children Up and Down then walk. This is the same ring model the
main window uses, packaged for dialogs so each one does not re-implement
the event filter.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QWidget

WIDGET_STOP = "widget"
GROUP_STOP = "group"
_FORWARD = 1
_BACK = -1


class DialogFocusRing(QObject):
    """Installs an application event filter scoped to one modal dialog.

    stops is called on every keypress so a re-rendered dialog never holds a
    stale ring; each entry is (WIDGET_STOP, widget) or (GROUP_STOP, holder).
    owns_updown marks widgets (a tree, a list) that keep their own vertical
    keys; Up and Down pass through while focus is inside one.
    """

    def __init__(
        self,
        dialog: QWidget,
        stops: Callable[[], list],
        owns_updown: Callable[[QWidget], bool] | None = None,
    ) -> None:
        super().__init__(dialog)
        self._dialog = dialog
        self._stops = stops
        self._owns_updown = owns_updown
        QApplication.instance().installEventFilter(self)

    def detach(self) -> None:
        QApplication.instance().removeEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        if QApplication.activeModalWidget() is not self._dialog:
            return False
        key = event.key()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if key == Qt.Key.Key_Right or (key == Qt.Key.Key_Tab and not shift):
            self._step(_FORWARD)
            return True
        if key in (Qt.Key.Key_Backtab, Qt.Key.Key_Left) or (
            key == Qt.Key.Key_Tab and shift
        ):
            self._step(_BACK)
            return True
        focus = QApplication.focusWidget()
        if key == Qt.Key.Key_Down:
            return self._step_within(focus, _FORWARD)
        if key == Qt.Key.Key_Up:
            return self._step_within(focus, _BACK)
        return False

    def _step(self, delta) -> None:
        stops = self._stops()
        index = self._current_index(stops)
        if index < 0:
            index = -1 if delta == _FORWARD else 0
        for _ in range(len(stops)):
            index = (index + delta) % len(stops)
            if self._focus_stop(stops[index]):
                return

    def _current_index(self, stops) -> int:
        focus = QApplication.focusWidget()
        if focus is None:
            return -1
        for index, (kind, target) in enumerate(stops):
            if kind == WIDGET_STOP and (target is focus or target.isAncestorOf(focus)):
                return index
            if kind == GROUP_STOP and target.isAncestorOf(focus):
                return index
        return -1

    def _focus_stop(self, stop) -> bool:
        kind, target = stop
        if kind == GROUP_STOP:
            focusables = self._focusables(target)
            if not focusables:
                return False
            focusables[0].setFocus(Qt.FocusReason.TabFocusReason)
            return True
        if not (target.isEnabled() and target.isVisible()):
            return False
        target.setFocus(Qt.FocusReason.TabFocusReason)
        return True

    @staticmethod
    def _focusables(holder: QWidget) -> list:
        return [
            widget
            for widget in holder.findChildren(QWidget)
            if widget.focusPolicy() != Qt.FocusPolicy.NoFocus
            and widget.isVisibleTo(holder)
            and widget.isEnabled()
        ]

    def _step_within(self, focus, delta) -> bool:
        if (
            focus is not None
            and self._owns_updown is not None
            and self._owns_updown(focus)
        ):
            return False
        for kind, target in self._stops():
            if kind != GROUP_STOP:
                continue
            focusables = self._focusables(target)
            if focus in focusables and len(focusables) > 1:
                index = (focusables.index(focus) + delta) % len(focusables)
                focusables[index].setFocus(Qt.FocusReason.TabFocusReason)
                return True
        return False
