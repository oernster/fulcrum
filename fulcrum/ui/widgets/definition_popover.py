"""A click-through popover showing a signal's full definition.

The definition text comes entirely from the domain SignalDefinition, so the UI
holds no glossary of its own.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from fulcrum.domain.signals import SignalDefinition
from fulcrum.ui import ui_scale

_POPOVER_WIDTH = 320


class DefinitionPopover(QFrame):
    """Frameless popover with the full definition of a signal."""

    def __init__(self, definition: SignalDefinition, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("Popover")
        self.setMaximumWidth(ui_scale.px(_POPOVER_WIDTH))
        layout = QVBoxLayout(self)

        title = QLabel(definition.label)
        title.setObjectName("Heading")
        layout.addWidget(title)

        gloss = QLabel(definition.gloss)
        gloss.setWordWrap(True)
        layout.addWidget(gloss)

        for caption, value in (
            ("Measures", definition.measures),
            ("Unit", definition.unit),
            ("Reads high when", definition.reads_high_when),
            ("Maps to", definition.maps_to),
        ):
            row = QLabel(f"<b>{caption}:</b> {value}")
            row.setWordWrap(True)
            layout.addWidget(row)
