"""Keyboard navigation across the main window: an explicit focus ring.

Built in the style of Meridian's QML navigation. Focus starts on an invisible
start item, so nothing is highlighted and no menu drops on launch; the first Tab
or Right enters the ring at the first menu. The ring runs the menu bar then the
body. Tab and Right step forward, Shift+Tab and Left step back, both wrapping.
Tab and Right ALWAYS move between top-level menus (File to Edit and so on), never
into a menu's vertical items, even while that menu is open: opening one and then
Tab closes it and moves to the next menu. Down and Up open the highlighted menu
and walk its items (left to the toolkit). The map and each list are a single
stop: the map consumes its own arrows, and Up and Down move within a focused
list. Installed as an application event filter, active only while the main window
is foreground.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

_MENU = "menu"
_WIDGET = "widget"
_GROUP = "group"
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
        self._map = map_view
        self._menu_actions = list(menu_actions)
        self._groups = list(groups)
        self._stops = [(_MENU, action) for action in self._menu_actions]
        self._stops += [(_WIDGET, widget) for widget in widget_stops]
        self._stops += [(_GROUP, group) for group in self._groups]
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Type.KeyPress or not self._window.isActiveWindow():
            return False
        key = event.key()
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            return self._handle_tab(key, event)
        if QApplication.activePopupWidget() is not None:
            return False  # the toolkit drives an open menu's items
        if QApplication.activeModalWidget() is not None:
            return False
        focus = QApplication.focusWidget()
        if focus is None or not self._within(focus):
            return False
        if focus is self._map:
            return False
        if focus is self._menubar:
            return self._handle_menu(key)
        return self._handle_arrows(focus, key)

    def _handle_tab(self, key, event) -> bool:
        shift = key == Qt.Key.Key_Backtab or bool(
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        )
        delta = _BACK if shift else _FORWARD
        popup = QApplication.activePopupWidget()
        if popup is not None:
            # Tab leaves an open menu for the next top-level menu, never its items.
            if not self._is_our_menu(popup):
                return False
            index = self._menu_index()
            popup.hide()
            self._step(delta, index)
            return True
        if QApplication.activeModalWidget() is not None:
            return False
        focus = QApplication.focusWidget()
        if focus is None or not self._within(focus):
            return False
        self._step(delta)
        return True

    def _handle_menu(self, key) -> bool:
        # Left and Right move between top-level menus; Down, Up, Enter and Escape
        # open and walk the menu items, so leave those to the toolkit.
        if key == Qt.Key.Key_Right:
            self._step(_FORWARD)
            return True
        if key == Qt.Key.Key_Left:
            self._step(_BACK)
            return True
        return False

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

    def _within(self, widget) -> bool:
        if widget is self._menubar:
            return True
        central = self._window.centralWidget()
        return central is not None and (
            widget is central or central.isAncestorOf(widget)
        )

    def _is_our_menu(self, popup) -> bool:
        return any(action.menu() is popup for action in self._menu_actions)

    def _menu_index(self) -> int:
        active = self._menubar.activeAction()
        for index, (kind, target) in enumerate(self._stops):
            if kind == _MENU and target is active:
                return index
        return 0

    def _step(self, delta, start=None) -> None:
        if not self._stops:
            return
        index = self._current_index() if start is None else start
        if index < 0:
            index = -1 if delta == _FORWARD else 0
        for _ in range(len(self._stops)):
            index = (index + delta) % len(self._stops)
            if self._focus_stop(self._stops[index]):
                return

    def _current_index(self) -> int:
        focus = QApplication.focusWidget()
        for index, (kind, target) in enumerate(self._stops):
            if kind == _MENU:
                if self._menubar.hasFocus() and self._menubar.activeAction() is target:
                    return index
            elif focus is not None and kind == _WIDGET and target is focus:
                return index
            elif focus is not None and kind == _GROUP and target.isAncestorOf(focus):
                return index
        return -1

    def _focus_stop(self, stop) -> bool:
        kind, target = stop
        if kind == _MENU:
            # Highlight the top-level menu without opening it; Down opens it.
            self._menubar.setFocus(Qt.FocusReason.TabFocusReason)
            self._menubar.setActiveAction(target)
            return True
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
