"""The board's map area: the complete picture by default, drill map beneath.

A stack of the two org views. The complete picture is the board's face:
clicking any domain on it hands over to the navigable drill map entered
straight at that section, Enter asks for the drill map (where the full
keyboard cursor lives) and climbing out of the top returns to the picture.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QStackedWidget

from fulcrum.application.game_session import GameSession
from fulcrum.domain.hierarchy import TOP_LEVEL_FOCUS, domain_has_teams
from fulcrum.domain.models import OrgState
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.auto_scroller import AutoScroller
from fulcrum.ui.widgets.complete_map_layout import (
    skipped_wrapper_id,
    summarized,
)
from fulcrum.ui.widgets.complete_map_view import CompleteMapView
from fulcrum.ui.widgets.org_editor_widgets import glyph_button
from fulcrum.ui.widgets.org_map_view import OrgMapView

_ZOOM_BUTTON_PX = 30
_ZOOM_MARGIN_PX = 10


class BoardMapPane(QStackedWidget):
    """Switches between the complete picture and the drill map."""

    # Re-emitted from the drill map: the domain now in focus, or None.
    drilled = Signal(object)

    def __init__(
        self, session_of: Callable[[], GameSession | None], parent=None
    ) -> None:
        super().__init__(parent)
        self._session_of = session_of
        self._complete = CompleteMapView()
        self._complete.domain_clicked.connect(self._drill_from_complete)
        self._complete.drill_requested.connect(self._enter_drill_mode)
        # A picture taller than the pane reads itself down at the app's
        # standard pace, exactly as the help dialogs do; the wheel, a drag,
        # a click or focus entering the map suspends the cycle in place.
        self._complete_scroller = AutoScroller(self._complete)
        self._map = OrgMapView()
        self._map.drilled.connect(self._on_drilled)
        self.addWidget(self._complete)
        self.addWidget(self._map)
        self.setFocusProxy(self._complete)
        # Corner zoom chips acting on whichever view is showing. They stay
        # out of the focus ring (the + and - keys are the keyboard route on
        # the focused map) so the explicit ring keeps only real stops.
        self._zoom_in = self._zoom_button("+", "Zoom in (+)")
        self._zoom_in.clicked.connect(self._on_zoom_in)
        self._zoom_out = self._zoom_button("-", "Zoom out (-)")
        self._zoom_out.clicked.connect(self._on_zoom_out)

    def _zoom_button(self, glyph: str, tip: str) -> QPushButton:
        # glyph_button paints the ink optically centred; plain button text
        # sits visibly off-centre in a small square chip.
        button = glyph_button(glyph, tip, "MapZoom")
        button.setParent(self)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    def _on_zoom_in(self) -> None:
        self._suspend_reader()
        self.currentWidget().zoom_in()

    def _on_zoom_out(self) -> None:
        self._suspend_reader()
        self.currentWidget().zoom_out()

    def _suspend_reader(self) -> None:
        """Zooming is reading by hand: pause the picture's self-reading."""
        if self.currentWidget() is self._complete:
            self._complete_scroller.suspend()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        size = ui_scale.px(_ZOOM_BUTTON_PX)
        margin = ui_scale.px(_ZOOM_MARGIN_PX)
        x = self.width() - size - margin
        self._zoom_in.setGeometry(x, margin, size, size)
        self._zoom_out.setGeometry(x, margin + size + margin, size, size)
        self._zoom_in.raise_()
        self._zoom_out.raise_()

    def set_org(self, org: OrgState) -> None:
        self._map.set_org(org)
        self._complete.set_org(org)

    def reset(self) -> None:
        """A fresh organisation: back to the top and the complete picture."""
        self._map.reset_view()
        self._set_drill(False)

    def apply_map_theme(self) -> None:
        self._map.apply_map_theme()
        self._complete.apply_map_theme()

    def sync_scope(self, focused: str | None) -> None:
        """Follow the Play-this-level toggle: top frame in, whole org out."""
        session = self._session_of()
        if session is None:
            return
        if focused == TOP_LEVEL_FOCUS:
            self._set_drill(True)
            self._map.reset_view()
            self._map.set_org(session.org)
        elif focused is None:
            self._set_drill(False)

    def _set_drill(self, drill: bool) -> None:
        view = self._map if drill else self._complete
        self.setCurrentWidget(view)
        self.setFocusProxy(view)
        self._zoom_in.raise_()
        self._zoom_out.raise_()

    def _drill_from_complete(self, domain_id: str) -> None:
        """A click on the complete picture drills straight into a section."""
        session = self._session_of()
        if session is None or not domain_has_teams(session.org, domain_id):
            return
        self._set_drill(True)
        self._map.set_org(session.org)
        self._map.drill_to(domain_id)

    def _enter_drill_mode(self) -> None:
        """Keyboard entry: the drill map, where the full node cursor lives.

        A single-company org enters at the company's own frame rather than
        showing one huge lone tile at the top.
        """
        session = self._session_of()
        if session is None:
            return
        self._set_drill(True)
        self._map.set_org(session.org)
        skipped = self._skipped_root()
        if skipped is not None and domain_has_teams(session.org, skipped):
            self._map.drill_to(skipped)
        self._map.setFocus(Qt.FocusReason.TabFocusReason)

    def _skipped_root(self) -> str | None:
        session = self._session_of()
        if session is None:
            return None
        return skipped_wrapper_id(session.org, summarized(session.org))

    def _on_drilled(self, domain_id) -> None:
        if domain_id is not None and domain_id == self._skipped_root():
            # Climbing into the lone skipped root would show the same tier
            # the picture already shows, so go straight back to it.
            self._map.reset_view()
            domain_id = None
        if domain_id is None:
            # Out of the top: the whole organisation is the complete
            # picture, so the board returns to it.
            self._set_drill(False)
        self.drilled.emit(domain_id)
