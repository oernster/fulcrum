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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
)

from fulcrum.application.dto import OrgBlueprint
from fulcrum.application.glossary import TERM_WORKLOAD, short_help
from fulcrum.application.name_pool import NamePicker
from fulcrum.application.org_draft import OrgDraft
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
_FRESH_TITLE = "Model my organisation"
_EDIT_TITLE = "Edit my organisation"
_HINT = (
    "Start a company, add items inside it with + or the right-click menu and "
    "set what each item is (a tier, your own label or Team) with the Type "
    "dropdown on the right. Unsure on a term? Open the "
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
        self.setMinimumSize(ui_scale.px(_MIN_WIDTH), ui_scale.px(_MIN_HEIGHT))
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
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._tree)
        splitter.addWidget(self._inspector)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([ui_scale.px(_TREE_PANE_W), ui_scale.px(_INSPECTOR_PANE_W)])
        layout.addWidget(splitter, 1)

        layout.addWidget(labelled(QLabel("Dependencies between teams")))
        self._deps = DependencyEditor()
        self._deps.set_teams(self._draft.teams())
        self._deps.set_dependencies(self._draft.dependencies)
        layout.addWidget(self._deps)

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

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        status = QVBoxLayout()
        self._totals = QLabel("")
        self._totals.setObjectName("Muted")
        status.addWidget(self._totals)
        self._warnings = QLabel("")
        self._warnings.setObjectName("Muted")
        self._warnings.setWordWrap(True)
        self._warnings.setOpenExternalLinks(False)
        self._warnings.linkActivated.connect(self._goto_warning)
        self._warnings.setVisible(False)
        status.addWidget(self._warnings)
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

    def _goto_warning(self, node_id: str) -> None:
        self._tree.select_node(node_id)

    def _open_glossary(self) -> None:
        GlossaryDialog(self).exec()

    def _refresh_footer(self) -> None:
        teams, people = self._draft.totals()
        self._totals.setText(f"{people:,} people across {teams} teams")
        warnings = self._draft.warnings()
        links = "<br>".join(
            f'<a href="{w.node_id}" style="color: {_ACCENT};">{w.message}</a>'
            for w in warnings
        )
        self._warnings.setText(links)
        self._warnings.setVisible(bool(warnings))
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
