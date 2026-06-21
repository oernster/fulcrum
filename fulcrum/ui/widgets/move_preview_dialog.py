"""A dialog that explains a candidate move and shows its before/after effect.

Opened by a move row's magnifier button. It reads the move's structural note and
verdict, scores the focused section before and after the move, names exactly what
changes and renders the affected teams as before/after maps with the changed nodes
ringed, so the player sees what the move does without committing it. The compute is
the same linear apply_move the board uses, quick enough to run on open.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.dto import MoveValuation
from fulcrum.application.interfaces import Simulator
from fulcrum.application.move_text import describe_move, move_note
from fulcrum.application.scope_analysis import active_org
from fulcrum.domain.hierarchy import focused_suborg, translate_focused_move
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, apply_move
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog
from fulcrum.ui.widgets.org_map_view import OrgMapView

_SCORE_DECIMALS = 1
_SKEW_DECIMALS = 2
_AFFECTED_CAP = 8
_DIALOG_W = 840
_DIALOG_H = 560
_CHANGE_COLOR = "#22d3ee"
_DECIDES = "decides locally"
_ESCALATES = "escalates"
_PLAY_LABEL = "Play this move"


class MovePreviewDialog(NeutralDialog):
    """Explains a move, names what changes and shows a ringed before/after map."""

    def __init__(
        self,
        org: OrgState,
        focus_id: str | None,
        valuation: MoveValuation,
        simulator: Simulator,
        active_before: OrgState,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preview move")
        if parent is not None:
            self.resize(parent.window().size())
        else:
            self.resize(ui_scale.px(_DIALOG_W), ui_scale.px(_DIALOG_H))
        real = translate_focused_move(org, focus_id, valuation.move)
        after_org = apply_move(org, real)
        before_score = simulator.score(active_before).value
        after_score = simulator.score(active_org(after_org, focus_id)).value
        before, after, ringed = self._views(
            org, after_org, real, active_before, focus_id
        )

        layout = QVBoxLayout(self)
        self._add_details(layout, active_before, valuation, before_score, after_score)
        self._add_changes(layout, org, after_org, real)
        layout.addWidget(self._before_after(before, after, ringed), 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        play = buttons.addButton(_PLAY_LABEL, QDialogButtonBox.ButtonRole.AcceptRole)
        play.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_details(
        self,
        layout: QVBoxLayout,
        active_before: OrgState,
        valuation: MoveValuation,
        before_score: float,
        after_score: float,
    ) -> None:
        heading = QLabel(describe_move(active_before, valuation.move))
        heading.setObjectName("Heading")
        layout.addWidget(heading)
        layout.addWidget(
            QLabel(
                f"{valuation.classification.value} · "
                f"{valuation.delta:+.{_SCORE_DECIMALS}f}  "
                f"({before_score:.{_SCORE_DECIMALS}f} → "
                f"{after_score:.{_SCORE_DECIMALS}f})"
            )
        )
        note = QLabel(move_note(valuation.move.kind))
        note.setWordWrap(True)
        layout.addWidget(note)

    def _add_changes(
        self, layout: QVBoxLayout, before_org: OrgState, after_org: OrgState, real: Move
    ) -> None:
        lines = self._changes(before_org, after_org, real)
        if not lines:
            return
        heading = QLabel("What changes")
        heading.setObjectName("Muted")
        layout.addWidget(heading)
        for line in lines:
            item = QLabel(line)
            item.setStyleSheet(f"color: {_CHANGE_COLOR};")
            item.setWordWrap(True)
            layout.addWidget(item)

    @staticmethod
    def _changes(before_org: OrgState, after_org: OrgState, real: Move) -> list[str]:
        after_by_id = {team.id: team for team in after_org.teams}
        lines: list[str] = []
        for team_id in real.targets[:_AFFECTED_CAP]:
            before = before_org.team(team_id)
            after = after_by_id.get(team_id)
            if after is None:
                lines.append(f"{before.name}: merged into another owner")
            elif before.has_local_authority != after.has_local_authority:
                now = _DECIDES if after.has_local_authority else _ESCALATES
                was = _ESCALATES if after.has_local_authority else _DECIDES
                lines.append(f"{before.name}: {was} → {now}")
            elif before.incentive_skew != after.incentive_skew:
                lines.append(
                    f"{before.name}: incentives "
                    f"{before.incentive_skew:.{_SKEW_DECIMALS}f} → "
                    f"{after.incentive_skew:.{_SKEW_DECIMALS}f}"
                )
        return lines

    @staticmethod
    def _views(
        org: OrgState,
        after_org: OrgState,
        real: Move,
        active_before: OrgState,
        focus_id: str | None,
    ) -> tuple[OrgState, OrgState, frozenset[str]]:
        if real.targets:
            domain_id = org.team(real.targets[0]).domain_id
            if domain_id is not None:
                return (
                    focused_suborg(org, domain_id),
                    focused_suborg(after_org, domain_id),
                    frozenset(real.targets),
                )
        return active_before, active_org(after_org, focus_id), frozenset()

    @staticmethod
    def _before_after(
        before: OrgState, after: OrgState, ringed: frozenset[str]
    ) -> QWidget:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        for label, section in (("Before", before), ("After", after)):
            column = QVBoxLayout()
            caption = QLabel(label)
            caption.setObjectName("Muted")
            column.addWidget(caption)
            view = OrgMapView()
            # Display-only here, so keep the view and its viewport out of the
            # tab chain: a focusable QGraphicsView (or its viewport) shows no
            # focus ring and reads as an invisible tab stop.
            view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            view.viewport().setFocusPolicy(Qt.FocusPolicy.NoFocus)
            view.set_org(section)
            view.set_highlight(ringed)
            column.addWidget(view, 1)
            wrapper = QWidget()
            wrapper.setLayout(column)
            row.addWidget(wrapper, 1)
        return holder
