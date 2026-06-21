"""A dialog to pick the rough size of a new random organisation."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from fulcrum.domain.org_size import DEFAULT_BAND, ORG_SIZE_BANDS, OrgSizeBand
from fulcrum.ui import ui_scale

_MIN_WIDTH = 440
_PROMPT = "Choose the rough size of the organisation to generate:"


class OrgSizePicker(QDialog):
    """Lists the size bands as radio choices and returns the one picked."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New random organisation")
        self.setMinimumWidth(ui_scale.px(_MIN_WIDTH))
        layout = QVBoxLayout(self)
        prompt = QLabel(_PROMPT)
        prompt.setObjectName("Muted")
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        self._group = QButtonGroup(self)
        for index, band in enumerate(ORG_SIZE_BANDS):
            button = QRadioButton(f"{band.label}   ·   {band.descriptor}")
            button.setChecked(band.key == DEFAULT_BAND.key)
            self._group.addButton(button, index)
            layout.addWidget(button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_band(self) -> OrgSizeBand:
        """The band whose radio button is currently chosen."""
        return ORG_SIZE_BANDS[self._group.checkedId()]

    @classmethod
    def choose(cls, parent=None) -> OrgSizeBand | None:
        """Show the picker; return the chosen band, or None if cancelled."""
        dialog = cls(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_band()
        return None
