"""Keyboard navigation across the main window: an explicit focus ring.

Built in the style of Meridian's QML navigation. Focus starts on an invisible
start item, so nothing is highlighted and no menu drops on launch; the first Tab
or Right enters the ring at the first control. Tab and Right step forward, Shift
Tab and Left step back, both wrapping at the ends. The map and each list are a
single stop: the map consumes its own arrow keys for node navigation, and Up and
Down move within the focused list. The menu bar stays on the standard Alt or F10,
not in the ring. Installed as an application event filter, it acts only while the
main window is foreground with no dialog or menu popup open.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

_WIDGET = "widget"
_GROUP = "group"
_FORWARD = 1
_BACK = -1


class KeyboardNavigator(QObject):
    """An application event filter that drives the main window's focus ring."""

    def __init__(self, window, widget_stops, groups, map_view) -> None:
        super().__init__(window)
        self._window = window
        self._map = map_view
        self._groups = list(groups)
        self._stops = [(_WIDGET, widget) for widget in widget_stops]
        self._stops += [(_GROUP, group) for group in self._groups]
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Type.KeyPress or not self._active():
            return False
        focus = QApplication.focusWidget()
        key = event.key()
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            shift = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            self._step(_BACK if key == Qt.Key.Key_Backtab or shift else _FORWARD)
            return True
        if focus is self._map:
            return False
        return self._handle_arrows(focus, key)

    def _handle_arrows(self, focus, key) -> bool:
        if key == Qt.Key.Key_Right:
            self._step(_FORWARD)
            return True
        if key == Qt.Key.Key_Left:
            self._step(_BACK)
            return True
        if key == Qt.Key.Key_Down:
            return self._within_group(focus, _FORWARD)
        if key == Qt.Key.Key_Up:
            return self._within_group(focus, _BACK)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and isinstance(
            focus, QPushButton
        ):
            focus.click()
            return True
        return False

    def _active(self) -> bool:
        if QApplication.activeModalWidget() is not None:
            return False
        if QApplication.activePopupWidget() is not None:
            return False
        if not self._window.isActiveWindow():
            return False
        focus = QApplication.focusWidget()
        central = self._window.centralWidget()
        return (
            focus is not None
            and central is not None
            and (focus is central or central.isAncestorOf(focus))
        )

    def _step(self, delta) -> None:
        if not self._stops:
            return
        index = self._current_index()
        if index < 0:
            index = -1 if delta == _FORWARD else 0
        for _ in range(len(self._stops)):
            index = (index + delta) % len(self._stops)
            if self._focus_stop(self._stops[index]):
                return

    def _current_index(self) -> int:
        focus = QApplication.focusWidget()
        if focus is None:
            return -1
        for index, (kind, target) in enumerate(self._stops):
            if kind == _WIDGET and target is focus:
                return index
            if kind == _GROUP and target.isAncestorOf(focus):
                return index
        return -1

    def _focus_stop(self, stop) -> bool:
        kind, target = stop
        if kind == _WIDGET:
            # A disabled stop (the undo button with no history) cannot hold
            # focus, so skip it rather than stall the ring on a dead stop.
            if not (target.isEnabled() and target.isVisible()):
                return False
            target.setFocus(Qt.FocusReason.TabFocusReason)
            return True
        children = self._focusable_children(target)
        if not children:
            return False
        children[0].setFocus(Qt.FocusReason.TabFocusReason)
        return True

    def _within_group(self, focus, delta) -> bool:
        for group in self._groups:
            children = self._focusable_children(group)
            if focus in children and len(children) > 1:
                index = (children.index(focus) + delta) % len(children)
                children[index].setFocus(Qt.FocusReason.TabFocusReason)
                return True
        return False

    def _focusable_children(self, group) -> list:
        return [
            widget
            for widget in group.findChildren(QWidget)
            if widget.focusPolicy() != Qt.FocusPolicy.NoFocus
            and widget.isVisibleTo(group)
            and widget.isEnabled()
        ]
