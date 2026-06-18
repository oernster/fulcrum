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

from fulcrum.application.planner import Guide
from fulcrum.ui import ui_scale

_MIN_WIDTH = 560
_MIN_HEIGHT = 420
_GROW_TOGGLE_TEXT = "Allow the organisation to grow (split or add teams)"

_ALREADY_GOOD = (
    "<p>This organisation is already in good shape; no single move improves "
    "it much from here.</p>"
)


def _guide_html(guide: Guide) -> str:
    rows = []
    for index, step in enumerate(guide.steps, start=1):
        rows.append(
            f"<tr><td>{index}.</td>"
            f"<td><b>{step.move.display_label()}</b></td>"
            f"<td>[{step.classification.value}]</td>"
            f"<td>&rarr; {step.score_after:.1f}</td></tr>"
        )
    body = (
        "<table cellspacing='6'>" + "".join(rows) + "</table>"
        if rows
        else _ALREADY_GOOD
    )
    return (
        "<h2>Path to a stronger org</h2>"
        f"<p><b>Start:</b> {guide.start_score:.1f} &nbsp;&nbsp; "
        f"<b>Final:</b> {guide.final_score:.1f}</p>"
        f"{body}"
    )


class GuideDialog(QDialog):
    """Lists the improving move chain, like a chess engine's best line.

    When a growth_guide is supplied a checkbox lets the player switch between the
    fixed-size plan and the plan that is also allowed to grow the org.
    """

    def __init__(
        self, guide: Guide, growth_guide: Guide | None = None, parent=None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guide - path to a stronger org")
        self.setMinimumSize(ui_scale.px(_MIN_WIDTH), ui_scale.px(_MIN_HEIGHT))
        self._guide = guide
        self._growth_guide = growth_guide
        layout = QVBoxLayout(self)
        if growth_guide is not None:
            toggle = QCheckBox(_GROW_TOGGLE_TEXT)
            toggle.toggled.connect(self._on_growth_toggled)
            layout.addWidget(toggle)
        self._browser = QTextBrowser()
        self._browser.setHtml(_guide_html(guide))
        layout.addWidget(self._browser)

        row = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        row.addStretch()
        row.addWidget(close_button)
        layout.addLayout(row)

    def _on_growth_toggled(self, allow_growth: bool) -> None:
        guide = self._growth_guide if allow_growth else self._guide
        self._browser.setHtml(_guide_html(guide))
