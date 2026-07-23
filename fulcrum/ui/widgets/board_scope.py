"""Presentation of the focused frame on the board.

Owns the widgets that explain WHERE the player is standing: the focus note,
the map caption, the drill-deeper nudge and the Play-this-level toggle that
scores the top level as its own frame. Split from BoardView so each module
stays within the structural line limit; the board composes this presenter
and keeps the analysis and rendering flow.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QLabel, QPushButton

from fulcrum.application.game_session import GameSession
from fulcrum.domain.hierarchy import TOP_LEVEL_FOCUS, child_domains
from fulcrum.domain.simulation import MoveClassification

_MAP_CAPTION = "Organisation map"
_MAP_HINT = "click a section to drill in"
_SCOPE_HINT = (
    "Nothing at this level grades good or better: structural value lives "
    "deeper. Drill into a domain on the map to find the moves that really "
    "gain."
)
_PLAY_LEVEL_LABEL = "Play this level"
_WHOLE_ORG_LABEL = "Score the whole org"
_PLAY_LEVEL_TIP = (
    "Score the top level as its own frame: each top-level unit becomes one "
    "actor and dependencies between them are priced."
)
_WHOLE_ORG_TIP = "Return to the flat whole-org score across every real team."
_TOP_LEVEL_NOTE = (
    "Focused on the top level: each top-level unit is one actor, so "
    "dependencies between them are priced here. Click a section to drill "
    "in; Score the whole org returns to the flat view."
)
PREVIEW_COLOR = "#fbbf24"


class ScopePresenter:
    """Creates and drives the frame-explaining widgets for the board."""

    def __init__(
        self,
        session_of: Callable[[], GameSession | None],
        scope_changed: Callable[[], None],
    ) -> None:
        self._session_of = session_of
        self._scope_changed = scope_changed
        self.focus_label = QLabel("")
        self.focus_label.setObjectName("Muted")
        self.focus_label.setWordWrap(True)
        self.focus_label.setVisible(False)
        self.map_caption = QLabel(_MAP_CAPTION)
        self.map_caption.setObjectName("Muted")
        self.level_button = QPushButton(_PLAY_LEVEL_LABEL)
        self.level_button.setToolTip(_PLAY_LEVEL_TIP)
        self.level_button.clicked.connect(self._toggle_top_level)
        self.level_button.setVisible(False)
        self.scope_hint = QLabel(_SCOPE_HINT)
        self.scope_hint.setObjectName("Muted")
        self.scope_hint.setWordWrap(True)
        self.scope_hint.setStyleSheet(f"color: {PREVIEW_COLOR};")
        self.scope_hint.setVisible(False)

    def refresh(self) -> None:
        """Re-render the level toggle, the focus note and the map caption."""
        self._update_level_button()
        self._set_focus_note()
        session = self._session_of()
        with_hint = session is not None and bool(session.org.domains)
        self.map_caption.setText(
            f"{_MAP_CAPTION} · {_MAP_HINT}" if with_hint else _MAP_CAPTION
        )
        self.map_caption.setStyleSheet("")

    def show_hint(self, text: str) -> None:
        """Show a transient status in the hint slot (computing, overview)."""
        self.scope_hint.setText(text)
        self.scope_hint.setVisible(True)

    def update_hint(self, valuations) -> None:
        """Show the drill-deeper nudge when this frame offers no strong move.

        Classification is absolute within the focused frame, so at an
        aggregate scope every move can honestly grade below good; the nudge
        turns that moment into the lesson (structural value lives in the
        sections) rather than a dead end. Hidden when there is nothing to
        drill into: at a leaf, weak moves are just weak moves.
        """
        session = self._session_of()
        if session is None:
            self.scope_hint.setVisible(False)
            return
        self.scope_hint.setText(_SCOPE_HINT)
        strong = {MoveClassification.GOOD, MoveClassification.GREAT}
        has_strong = any(v.classification in strong for v in valuations)
        focused = session.focused_on
        if focused == TOP_LEVEL_FOCUS:
            can_drill = bool(session.org.domains)
        else:
            can_drill = bool(child_domains(session.org, focused))
        self.scope_hint.setVisible(can_drill and not has_strong)

    def _toggle_top_level(self) -> None:
        """Switch between the flat whole-org score and the top-level frame."""
        session = self._session_of()
        if session is None:
            return
        playing = session.focused_on == TOP_LEVEL_FOCUS
        session.focus(None if playing else TOP_LEVEL_FOCUS)
        self._update_level_button()
        self._set_focus_note()
        self._scope_changed()

    def _update_level_button(self) -> None:
        """The toggle exists only at the top of a hierarchical org."""
        session = self._session_of()
        if session is None:
            self.level_button.setVisible(False)
            return
        focused = session.focused_on
        at_top = focused is None or focused == TOP_LEVEL_FOCUS
        self.level_button.setVisible(at_top and bool(session.org.domains))
        playing = focused == TOP_LEVEL_FOCUS
        self.level_button.setText(_WHOLE_ORG_LABEL if playing else _PLAY_LEVEL_LABEL)
        self.level_button.setToolTip(_WHOLE_ORG_TIP if playing else _PLAY_LEVEL_TIP)

    def _set_focus_note(self) -> None:
        session = self._session_of()
        focused = session.focused_on if session is not None else None
        if focused is None:
            self.focus_label.setVisible(False)
            self.focus_label.setStyleSheet("")
            self.focus_label.setText("")
            return
        if focused == TOP_LEVEL_FOCUS:
            text = _TOP_LEVEL_NOTE
        else:
            name = self._domain_name(session, focused)
            text = (
                f"Focused on {name}: this score and these moves are the "
                "section's. Click a section to drill in; use Back on the map "
                "to climb out."
            )
        self.focus_label.setText(text)
        self.focus_label.setStyleSheet(f"color: {PREVIEW_COLOR};")
        self.focus_label.setVisible(True)

    @staticmethod
    def _domain_name(session: GameSession, domain_id: str) -> str:
        for domain in session.org.domains:
            if domain.id == domain_id:
                return domain.name
        return domain_id
