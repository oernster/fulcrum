"""The 'Model my organisation' wizard: collect an OrgBlueprint from the user.

The user describes structure in plain terms (team count, who ships without
asking, how skewed incentives are, the typical wait at a boundary); the wizard
returns a blueprint that the application layer compiles into an OrgState. Team
owners are pre-filled from the shared name pool, so a wizard-built org never
shows a blank owner.
"""

from __future__ import annotations

from random import Random

from PySide6.QtWidgets import (
    QCheckBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from fulcrum.application.dto import DependencySpec, OrgBlueprint, TeamSpec
from fulcrum.application.glossary import (
    TERM_INCENTIVE_SKEW,
    TERM_LOCAL_AUTHORITY,
    short_help,
)
from fulcrum.application.name_pool import NamePicker
from fulcrum.ui import ui_scale

_WIZARD_MIN_WIDTH = 640

_MIN_TEAMS = 2
_MAX_TEAMS = 8
_DEFAULT_TEAMS = 4
_MIN_WORKLOAD = 1
_MAX_WORKLOAD = 20
_DEFAULT_WORKLOAD = 6
_MIN_DELAY = 0
_MAX_DELAY = 10
_DEFAULT_DELAY = 4
_MAX_SKEW_PERCENT = 100
_DEFAULT_SKEW_PERCENT = 40
_PERCENT = 100.0

_COL_NAME = 0
_COL_AUTHORITY = 1
_COL_SKEW = 2
_COLUMN_HEADERS = ("Team name", "Ships without asking", "Incentive skew %")

_FIELD_TEAMS = "team_count"
_FIELD_WORKLOAD = "workload"
_FIELD_DELAY = "delay"


def _labelled_spin(layout, caption, minimum, maximum, value):
    layout.addWidget(QLabel(caption))
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    layout.addWidget(spin)
    return spin


def _skew_spin() -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(0, _MAX_SKEW_PERCENT)
    spin.setValue(_DEFAULT_SKEW_PERCENT)
    return spin


class _BasicsPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Your organisation")
        self.setSubTitle("Start with the broad shape; refine the teams next.")
        layout = QVBoxLayout(self)
        self._teams = _labelled_spin(
            layout,
            "How many teams ship independently?",
            _MIN_TEAMS,
            _MAX_TEAMS,
            _DEFAULT_TEAMS,
        )
        self._workload = _labelled_spin(
            layout,
            "Decisions arriving per team each turn (workload)",
            _MIN_WORKLOAD,
            _MAX_WORKLOAD,
            _DEFAULT_WORKLOAD,
        )
        self._delay = _labelled_spin(
            layout,
            "Typical wait at a team boundary (turns)",
            _MIN_DELAY,
            _MAX_DELAY,
            _DEFAULT_DELAY,
        )
        self.registerField(_FIELD_TEAMS, self._teams)
        self.registerField(_FIELD_WORKLOAD, self._workload)
        self.registerField(_FIELD_DELAY, self._delay)


class _TeamsPage(QWizardPage):
    def __init__(self, names: NamePicker) -> None:
        super().__init__()
        self._names = names
        self.setTitle("The teams")
        self.setSubTitle("Tick the teams that can ship without escalating.")
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, len(_COLUMN_HEADERS))
        self._table.setHorizontalHeaderLabels(list(_COLUMN_HEADERS))
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(_COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            _COL_AUTHORITY, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(_COL_SKEW, QHeaderView.ResizeMode.ResizeToContents)
        header_item = self._table.horizontalHeaderItem(_COL_AUTHORITY)
        header_item.setToolTip(short_help(TERM_LOCAL_AUTHORITY))
        skew_item = self._table.horizontalHeaderItem(_COL_SKEW)
        skew_item.setToolTip(short_help(TERM_INCENTIVE_SKEW))
        layout.addWidget(self._table)

    def initializePage(self) -> None:
        count = self.field(_FIELD_TEAMS)
        self._table.setRowCount(count)
        for row in range(count):
            name = QLineEdit()
            name.setText(f"Team {row + 1}")
            self._table.setCellWidget(row, _COL_NAME, name)
            self._table.setCellWidget(row, _COL_AUTHORITY, QCheckBox())
            self._table.setCellWidget(row, _COL_SKEW, _skew_spin())

    def teams(self) -> tuple[TeamSpec, ...]:
        specs = []
        for row in range(self._table.rowCount()):
            name = self._table.cellWidget(row, _COL_NAME).text() or f"Team {row + 1}"
            authority = self._table.cellWidget(row, _COL_AUTHORITY).isChecked()
            skew = self._table.cellWidget(row, _COL_SKEW).value() / _PERCENT
            specs.append(
                TeamSpec(
                    id=f"team_{row + 1}",
                    name=name,
                    has_local_authority=authority,
                    incentive_skew=skew,
                    owner=self._names.draw(),
                )
            )
        return tuple(specs)


class OrgWizard(QWizard):
    """Collects an OrgBlueprint describing the user's current organisation."""

    def __init__(self, parent=None, rng: Random | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Model my organisation")
        # ClassicStyle drops the native Aero chrome (the white footer, the small
        # top-left back arrow and title icon) so the dark theme applies cleanly;
        # the first page has nothing to go back to, so it carries no Back button.
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.setMinimumWidth(ui_scale.px(_WIZARD_MIN_WIDTH))
        self._basics = _BasicsPage()
        self._teams = _TeamsPage(NamePicker(rng if rng is not None else Random()))
        self.addPage(self._basics)
        self.addPage(self._teams)

    def to_blueprint(self) -> OrgBlueprint:
        teams = self._teams.teams()
        delay = self.field(_FIELD_DELAY)
        workload = self.field(_FIELD_WORKLOAD)
        dependencies = tuple(
            DependencySpec(teams[i].id, teams[i + 1].id, delay)
            for i in range(len(teams) - 1)
        )
        return OrgBlueprint(teams=teams, dependencies=dependencies, workload=workload)
