"""A dialog showing the planner's guide: the path to a stronger org."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from fulcrum.application.dto import MoveValuation
from fulcrum.application.interfaces import Simulator
from fulcrum.application.planner import Guide
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.move_preview_dialog import MovePreviewDialog

_MIN_WIDTH = 560
_MIN_HEIGHT = 420
_GROW_TOGGLE_TEXT = "Allow the organisation to grow (split or add teams)"
_PREVIEW_ICON = "🔍"
_PREVIEW_COLOR = "#f59e0b"
_PREVIEW_PREFIX = "preview:"

_ALREADY_GOOD = (
    "<p>This organisation is already in good shape; no single move improves "
    "it much from here.</p>"
)


def _guide_html(guide: Guide) -> str:
    head = (
        "<h2>Path to a stronger org</h2>"
        f"<p><b>Start:</b> {guide.start_score:.1f} &nbsp;&nbsp; "
        f"<b>Final:</b> {guide.final_score:.1f}</p>"
    )
    if not guide.steps:
        return head + _ALREADY_GOOD
    rows = []
    for index, step in enumerate(guide.steps):
        link = (
            f"<a href='{_PREVIEW_PREFIX}{index}' "
            f"style='color:{_PREVIEW_COLOR}; text-decoration:none;'>"
            f"{_PREVIEW_ICON}</a>"
        )
        rows.append(
            f"<tr><td>{index + 1}.</td>"
            f"<td><b>{step.move.display_label()}</b></td>"
            f"<td>[{step.classification.value}]</td>"
            f"<td>&rarr; {step.score_after:.1f}</td>"
            f"<td>{link}</td></tr>"
        )
    hint = f"<p>{_PREVIEW_ICON} previews a move.</p>"
    return head + hint + "<table cellspacing='6'>" + "".join(rows) + "</table>"


class GuideDialog(QDialog):
    """Lists the improving move chain, like a chess engine's best line.

    When a growth_guide is supplied a checkbox lets the player switch between the
    fixed-size plan and the plan that is also allowed to grow the org. Each step
    carries a magnifier that previews the move, as the board's move rows do.
    """

    def __init__(
        self,
        guide: Guide,
        growth_guide: Guide | None = None,
        simulator: Simulator | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guide - path to a stronger org")
        self.setMinimumSize(ui_scale.px(_MIN_WIDTH), ui_scale.px(_MIN_HEIGHT))
        self._guide = guide
        self._growth_guide = growth_guide
        self._simulator = simulator
        self._current = guide
        layout = QVBoxLayout(self)
        if growth_guide is not None:
            toggle = QCheckBox(_GROW_TOGGLE_TEXT)
            toggle.toggled.connect(self._on_growth_toggled)
            layout.addWidget(toggle)
        self._browser = QTextBrowser()
        self._browser.setOpenLinks(False)
        self._browser.anchorClicked.connect(self._on_anchor)
        self._browser.setHtml(_guide_html(guide))
        layout.addWidget(self._browser)

        row = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        row.addStretch()
        row.addWidget(close_button)
        layout.addLayout(row)

    def _on_growth_toggled(self, allow_growth: bool) -> None:
        self._current = self._growth_guide if allow_growth else self._guide
        self._browser.setHtml(_guide_html(self._current))

    def _on_anchor(self, url) -> None:
        text = url.toString()
        if self._simulator is None or not text.startswith(_PREVIEW_PREFIX):
            return
        index = int(text.split(":", 1)[1])
        if index < 0 or index >= len(self._current.steps):
            return
        step = self._current.steps[index]
        valuation = MoveValuation(
            step.move, step.score_before, step.score_after, step.classification
        )
        MovePreviewDialog(
            step.org_before, None, valuation, self._simulator, step.org_before, self
        ).exec()
