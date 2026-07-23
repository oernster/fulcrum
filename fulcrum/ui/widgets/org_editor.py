"""The two-pane 'Model my organisation' editor.

The left pane is the org tree: the structure being built, visible as a
structure. The right pane is the inspector for the selected node. The footer
carries the live rollup, the warnings and the OK gating. The dialog is a pure
function of an OrgBlueprint: seeded fresh for a new model or populated from
the current org for round-trip editing, and it serialises back to the same
blueprint shape either way.
"""

from __future__ import annotations

from random import Random

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.dto import OrgBlueprint
from fulcrum.application.glossary import TERM_WORKLOAD, short_help
from fulcrum.application.name_pool import NamePicker
from fulcrum.application.org_draft import OrgDraft
from fulcrum.shared.text import count_noun
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.dependency_editor import DependencyEditor
from fulcrum.ui.widgets.glossary_dialog import GlossaryDialog
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog
from fulcrum.ui.widgets.org_editor_widgets import labelled
from fulcrum.ui.widgets.org_inspector import OrgInspectorPane
from fulcrum.ui.widgets.org_tree_pane import OrgTreePane

_ACCENT = "#f59e0b"
_MIN_WIDTH = 1000
_MIN_HEIGHT = 640
_MIN_WORKLOAD = 1
_MAX_WORKLOAD = 50
_TREE_PANE_W = 560
_INSPECTOR_PANE_W = 400
# Modelling needs room: the dialog opens at nearly the whole app window (or
# screen, when there is no parent) and carries a maximise button, so the tree
# workspace scales to the organisation rather than to a fixed dialog.
_PARENT_FILL = 0.95
_SCREEN_FILL = 0.90
# The structure rows dominate the dependency rows; the splitter lets the user
# rebalance.
_STRUCTURE_SHARE = 3
_DEPS_SHARE = 1
_STRUCTURE_ROW_H = 460
_DEPS_ROW_H = 220
_FRESH_TITLE = "Model my organisation"
_EDIT_TITLE = "Edit my organisation"
_HINT = (
    "Start at any tier from the New dropdown (a whole company down to a "
    "single team), add items inside a unit with + or the right-click menu "
    "and set what each item is (a tier, your own label or Team) with the "
    "Type dropdown on the right. Unsure on a term? Open the "
    f'<a href="#glossary" style="color: {_ACCENT};">decision glossary</a>.'
)


class OrgEditorDialog(NeutralDialog):
    """Collects a hierarchical OrgBlueprint: groups, teams, dependencies."""

    def __init__(
        self,
        parent=None,
        blueprint: OrgBlueprint | None = None,
        rng: Random | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_EDIT_TITLE if blueprint is not None else _FRESH_TITLE)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setMinimumSize(ui_scale.px(_MIN_WIDTH), ui_scale.px(_MIN_HEIGHT))
        self.resize(self._initial_size(parent))
        names = NamePicker(rng if rng is not None else Random())
        if blueprint is not None:
            self._draft = OrgDraft.from_blueprint(blueprint, names)
        else:
            self._draft = OrgDraft(names)
            company = self._draft.add_container(None)
            self._draft.add_team(company.id)

        layout = QVBoxLayout(self)
        hint = QLabel(_HINT)
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        hint.setOpenExternalLinks(False)
        hint.linkActivated.connect(self._open_glossary)
        layout.addWidget(hint)

        self._tree = OrgTreePane(self._draft)
        self._inspector = OrgInspectorPane(self._draft)
        panes = QSplitter(Qt.Orientation.Horizontal)
        panes.addWidget(self._tree)
        panes.addWidget(self._inspector)
        panes.setStretchFactor(0, 1)
        panes.setStretchFactor(1, 0)
        panes.setSizes([ui_scale.px(_TREE_PANE_W), ui_scale.px(_INSPECTOR_PANE_W)])

        self._deps = DependencyEditor()
        self._deps.set_teams(self._draft.teams())
        self._deps.set_dependencies(self._draft.dependencies)
        deps_box = QWidget()
        deps_layout = QVBoxLayout(deps_box)
        deps_layout.setContentsMargins(0, 0, 0, 0)
        deps_layout.addWidget(labelled(QLabel("Dependencies between teams")))
        deps_layout.addWidget(self._deps)

        body = QSplitter(Qt.Orientation.Vertical)
        body.addWidget(panes)
        body.addWidget(deps_box)
        body.setStretchFactor(0, _STRUCTURE_SHARE)
        body.setStretchFactor(1, _DEPS_SHARE)
        body.setSizes([ui_scale.px(_STRUCTURE_ROW_H), ui_scale.px(_DEPS_ROW_H)])
        layout.addWidget(body, 1)

        workload_row = QHBoxLayout()
        workload_label = QLabel("Decisions arriving per team each turn")
        workload_label.setToolTip(short_help(TERM_WORKLOAD))
        workload_row.addWidget(workload_label)
        self._workload = QSpinBox()
        self._workload.setRange(_MIN_WORKLOAD, _MAX_WORKLOAD)
        self._workload.setValue(self._draft.workload)
        self._workload.setToolTip(short_help(TERM_WORKLOAD))
        workload_row.addWidget(self._workload)
        workload_row.addStretch()
        layout.addLayout(workload_row)

        layout.addLayout(self._build_footer())

        self._tree.nodeSelected.connect(self._inspector.set_node)
        self._tree.structureChanged.connect(self._structure_changed)
        self._inspector.nodeEdited.connect(self._node_edited)
        self._inspector.kindChanged.connect(self._kind_changed)
        self._refresh_footer()

    @staticmethod
    def _initial_size(parent) -> QSize:
        """Nearly the app window's size, or the screen's when parentless."""
        if parent is not None:
            base = parent.window().size()
            return QSize(
                round(base.width() * _PARENT_FILL),
                round(base.height() * _PARENT_FILL),
            )
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry().size()
        return QSize(
            round(available.width() * _SCREEN_FILL),
            round(available.height() * _SCREEN_FILL),
        )

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        status = QVBoxLayout()
        self._totals = QLabel("")
        self._totals.setObjectName("Muted")
        status.addWidget(self._totals)
        self._reason = QLabel("")
        self._reason.setObjectName("BlockedReason")
        self._reason.setVisible(False)
        status.addWidget(self._reason)
        footer.addLayout(status, 1)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        footer.addWidget(
            self._buttons, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight
        )
        return footer

    # ---------------------------------------------------------------- events

    def _structure_changed(self) -> None:
        self._deps.set_teams(self._draft.teams())
        self._inspector.set_node(self._tree.selected_id())
        self._refresh_footer()

    def _node_edited(self, _node_id: str) -> None:
        self._tree.update_labels()
        self._deps.set_teams(self._draft.teams())
        self._refresh_footer()

    def _kind_changed(self, node_id: str) -> None:
        """An item was converted between team and unit: re-render around it."""
        self._tree.rebuild()
        self._tree.select_node(node_id)
        self._inspector.set_node(node_id)
        self._deps.set_teams(self._draft.teams())
        self._refresh_footer()

    def _open_glossary(self) -> None:
        GlossaryDialog(self).exec()

    def _refresh_footer(self) -> None:
        teams, people = self._draft.totals()
        self._totals.setText(
            f"{count_noun(people, 'person', 'people')} across "
            f"{count_noun(teams, 'team')}"
        )
        reason = self._draft.blocking_reason()
        self._reason.setText(reason or "")
        self._reason.setVisible(reason is not None)
        ok = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(reason is None)

    # ---------------------------------------------------------------- output

    def to_blueprint(self) -> OrgBlueprint:
        self._draft.workload = self._workload.value()
        self._draft.dependencies = self._deps.dependencies()
        return self._draft.to_blueprint()
