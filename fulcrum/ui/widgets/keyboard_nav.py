"""Keyboard navigation across the main window: one explicit focus ring.

Tab and Right step forward; Shift+Tab and Left step back. They are the same ring
throughout: the menu titles (File, Edit, View, Help), then the body controls, the
map and the lists, wrapping at both ends. Right and Left are handled identically
to Tab and Shift+Tab at the top of the filter, so the menu bar never falls back to
its native left/right menu cycling. Down opens a highlighted menu; the toolkit
then walks its items. The map keeps its own arrow keys for node navigation (so
Right and Left are left to it; Tab still carries focus out), and Up and Down move
within a focused list. Installed as an application event filter, active only while
the main window is foreground.
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
        if QApplication.activeModalWidget() is not None:
            return False
        key = event.key()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        popup = QApplication.activePopupWidget()
        if popup is not None:
            # The toolkit walks an open menu's items; Tab still steps the ring to
            # the next or previous top-level menu.
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and self._is_our_menu(popup):
                index = self._menu_index()
                popup.hide()
                self._step(
                    _BACK if key == Qt.Key.Key_Backtab or shift else _FORWARD, index
                )
                return True
            return False
        focus = QApplication.focusWidget()
        on_menu = self._menubar.activeAction() is not None
        on_map = (not on_menu) and focus is self._map
        if self._is_forward(key, shift, on_map):
            self._step(_FORWARD)
            return True
        if self._is_back(key, shift, on_map):
            self._step(_BACK)
            return True
        if on_menu or on_map:
            return False  # the toolkit opens the menu; the map walks its nodes
        if focus is None or not self._within(focus):
            return False
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

    @staticmethod
    def _is_forward(key, shift, on_map) -> bool:
        if key == Qt.Key.Key_Tab and not shift:
            return True
        return key == Qt.Key.Key_Right and not on_map

    @staticmethod
    def _is_back(key, shift, on_map) -> bool:
        if key == Qt.Key.Key_Backtab:
            return True
        if key == Qt.Key.Key_Tab and shift:
            return True
        return key == Qt.Key.Key_Left and not on_map

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
        active = self._menubar.activeAction()
        focus = QApplication.focusWidget()
        for index, (kind, target) in enumerate(self._stops):
            if kind == _MENU:
                if active is not None and target is active:
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
        # Leaving the menu bar: clear its highlight so it is no longer the active
        # region, otherwise it keeps consuming the arrow keys as native menu nav.
        self._menubar.setActiveAction(None)
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
