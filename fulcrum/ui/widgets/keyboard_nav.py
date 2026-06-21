"""Keyboard navigation across the main window: a focus ring plus arrow mirroring.

Focus starts on the menu bar. Tab or Right steps forward through the menus, the
top action buttons, the take-a-move-back button, the map, the moves and the
signals, wrapping at the end; Shift+Tab or Left steps back. Up and Down move
within the current group (the moves or the signals list). The map handles its own
arrow keys to move its node cursor, so the ring leaves its arrows alone and only
Tab carries focus out of it. Installed as an application event filter, it acts
only while the main window is active and no dialog or menu popup is open.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

_MENU = "menu"
_WIDGET = "widget"
_FORWARD = 1
_BACK = -1


class KeyboardNavigator(QObject):
    """An application event filter that drives the main window's focus ring."""

    def __init__(
        self, window, menubar, menu_actions, widget_stops, groups, map_view
    ) -> None:
        super().__init__(window)
        self._window = window
        self._menubar = menubar
        self._menu_actions = list(menu_actions)
        self._widget_stops = list(widget_stops)
        self._groups = list(groups)
        self._map = map_view
        QApplication.instance().installEventFilter(self)

    def focus_start(self) -> None:
        """Put focus on the first menu, the top-left start of the ring."""
        if self._menu_actions:
            self._focus_stop((_MENU, self._menu_actions[0]))

    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Type.KeyPress or not self._active():
            return False
        focus = QApplication.focusWidget()
        key = event.key()
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            shift = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            self._move(_BACK if key == Qt.Key.Key_Backtab or shift else _FORWARD)
            return True
        if focus is self._map:
            return False
        return self._handle_key(focus, key)

    def _handle_key(self, focus, key) -> bool:
        if key == Qt.Key.Key_Right:
            self._move(_FORWARD)
            return True
        if key == Qt.Key.Key_Left:
            self._move(_BACK)
            return True
        if key == Qt.Key.Key_Down:
            return self._move_within_group(focus, _FORWARD)
        if key == Qt.Key.Key_Up:
            return self._move_within_group(focus, _BACK)
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
        return focus is not None and self._within(focus)

    def _within(self, widget) -> bool:
        if widget is self._menubar:
            return True
        central = self._window.centralWidget()
        return central is not None and (
            widget is central or central.isAncestorOf(widget)
        )

    def _flat_stops(self) -> list:
        stops = [(_MENU, action) for action in self._menu_actions]
        stops += [(_WIDGET, widget) for widget in self._widget_stops]
        for group in self._groups:
            stops += [(_WIDGET, child) for child in self._focusable_children(group)]
        return stops

    def _focusable_children(self, group) -> list:
        return [
            widget
            for widget in group.findChildren(QWidget)
            if widget.focusPolicy() != Qt.FocusPolicy.NoFocus
            and widget.isVisibleTo(group)
            and widget.isEnabled()
        ]

    def _current_index(self, stops) -> int:
        focus = QApplication.focusWidget()
        if focus is None:
            return -1
        for index, (kind, target) in enumerate(stops):
            if kind == _MENU:
                if self._menubar.hasFocus() and self._menubar.activeAction() is target:
                    return index
            elif target is focus or target.isAncestorOf(focus):
                return index
        return -1

    def _move(self, delta) -> None:
        stops = self._flat_stops()
        if not stops:
            return
        index = self._current_index(stops)
        target = stops[0] if index < 0 else stops[(index + delta) % len(stops)]
        self._focus_stop(target)

    def _move_within_group(self, focus, delta) -> bool:
        for group in self._groups:
            children = self._focusable_children(group)
            if focus in children and len(children) > 1:
                index = (children.index(focus) + delta) % len(children)
                children[index].setFocus(Qt.FocusReason.TabFocusReason)
                return True
        return False

    def _focus_stop(self, stop) -> None:
        kind, target = stop
        if kind == _MENU:
            self._menubar.setFocus(Qt.FocusReason.TabFocusReason)
            self._menubar.setActiveAction(target)
        else:
            target.setFocus(Qt.FocusReason.TabFocusReason)
