"""Help dialog: what grounds every number in the model.

The content comes from the application provenance module, which reads every
value live from the parameter objects; this dialog only renders it. Joins
the help family: auto-scrolls gently and yields to any manual scroll.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from fulcrum.application.provenance import (
    build_provenance,
    fragility_text,
    intro_text,
)
from fulcrum.shared.resources import find_provenance_png
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.auto_scroller import AutoScroller
from fulcrum.ui.widgets.dialog_banner import banner_row
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog

_TITLE = "What grounds the numbers"
_MIN_WIDTH = 720
_MIN_HEIGHT = 560


def _provenance_html() -> str:
    # The title lives in the identity banner above the browser.
    parts = [f"<p>{intro_text()}</p>"]
    parts.append("<h3>The numbers, one by one</h3>")
    for entry in build_provenance():
        parts.append(
            f"<p><b>{entry.term}</b><br>{entry.does}<br>"
            f"<i>Mechanism:</i> {entry.mechanism}<br>"
            f"<i>Magnitude:</i> {entry.magnitude}</p>"
        )
    parts.append("<h3>How fragile is this?</h3>")
    parts.append(f"<p>{fragility_text()}</p>")
    return "".join(parts)


class ProvenanceDialog(NeutralDialog):
    """Shows every coefficient with its source, grounding and fragility."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_TITLE)
        self.setMinimumSize(ui_scale.px(_MIN_WIDTH), ui_scale.px(_MIN_HEIGHT))
        layout = QVBoxLayout(self)
        # The identity banner: the golden kin beside the accent title, in
        # the same manner as the move record's banner.
        layout.addLayout(banner_row(find_provenance_png(), _TITLE))
        browser = QTextBrowser()
        browser.setHtml(_provenance_html())
        layout.addWidget(browser)
        self._scroller = AutoScroller(browser)

        row = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        row.addStretch()
        row.addWidget(close_button)
        layout.addLayout(row)
