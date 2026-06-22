"""A dialog showing one signal's definition, opened from its magnifier button.

Replaces the old hover popover. A click-opened dialog reads clearly on every
platform and scrolls when tall, neither of which the hover tooltip managed
reliably; the magnifier that opens it sits in the keyboard focus ring.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from fulcrum.domain.signals import SignalReading
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog

_MIN_WIDTH = 460
_MIN_HEIGHT = 320
_VALUE_DECIMALS = 1


class SignalDetailDialog(NeutralDialog):
    """One signal explained: its reading, what it measures and how to read it."""

    def __init__(self, reading: SignalReading, parent=None) -> None:
        super().__init__(parent)
        definition = reading.definition
        self.setWindowTitle(definition.label)
        self.setMinimumSize(ui_scale.px(_MIN_WIDTH), ui_scale.px(_MIN_HEIGHT))
        layout = QVBoxLayout(self)

        content = QWidget()
        inner = QVBoxLayout(content)
        heading = QLabel(definition.label)
        heading.setObjectName("Heading")
        inner.addWidget(heading)
        reading_label = QLabel(
            f"Current reading: {reading.value:.{_VALUE_DECIMALS}f} {definition.unit}"
        )
        reading_label.setObjectName("Muted")
        inner.addWidget(reading_label)
        gloss = QLabel(definition.gloss)
        gloss.setWordWrap(True)
        inner.addWidget(gloss)
        for caption, text in (
            ("Measures", definition.measures),
            ("Unit", definition.unit),
            ("Reads high when", definition.reads_high_when),
            ("Maps to", definition.maps_to),
        ):
            row = QLabel(f"<b>{caption}:</b> {text}")
            row.setWordWrap(True)
            inner.addWidget(row)
        inner.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
