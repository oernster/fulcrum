"""The org editor's left pane: the organisation rendered as a live tree.

Every node shows its category, name and a rolled-up badge; containers carry an
inline + (add a team or sub-group) and every node a - (remove, behind a
confirm). The context menu adds Duplicate, Move up, Move down and Move to. The
pane is a thin view over the OrgDraft: every operation calls the draft then
rebuilds, so the tree always reflects the model.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.org_draft import OrgDraft
from fulcrum.application.org_draft_nodes import ContainerDraft
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.org_editor_widgets import action_button

_ROLE_ID = int(Qt.ItemDataRole.UserRole)
_COL_LABEL = 0
_COL_ACTIONS = 1
_ACTIONS_COLUMN_WIDTH = 44
_ACTION_SPACING = 2
_WARNING_BADGE = " \N{WARNING SIGN}"
_TOP_LEVEL_LABEL = "(top level)"
_ADD_TEAM_TEXT = "Add a team here"
_ADD_SUBGROUP_TEXT = "Add a sub-group here"


class OrgTreePane(QWidget):
    """Shows the draft as a tree and applies structural edits to it."""

    nodeSelected = Signal(str)
    structureChanged = Signal()

    def __init__(self, draft: OrgDraft, parent=None) -> None:
        super().__init__(parent)
        self._draft = draft
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(2)
        self._tree.setHeaderHidden(True)
        self._tree.setColumnWidth(_COL_ACTIONS, ui_scale.px(_ACTIONS_COLUMN_WIDTH))
        self._tree.header().setStretchLastSection(False)
        self._tree.header().setSectionResizeMode(
            _COL_LABEL, QHeaderView.ResizeMode.Stretch
        )
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._context_menu)
        self._tree.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self._tree, 1)

        row = QHBoxLayout()
        add_group = QPushButton("Add a group")
        add_group.setToolTip("Start a new top-level group")
        add_group.clicked.connect(self._add_root_group)
        expand = QPushButton("Expand all")
        expand.clicked.connect(self._tree.expandAll)
        collapse = QPushButton("Collapse all")
        collapse.clicked.connect(self._tree.collapseAll)
        row.addWidget(add_group)
        row.addWidget(expand)
        row.addWidget(collapse)
        row.addStretch()
        layout.addLayout(row)

        self.rebuild()

    # ------------------------------------------------------------- rendering

    def rebuild(self) -> None:
        """Re-render the whole tree, preserving expansion and selection."""
        expanded = self._expanded_ids()
        selected = self.selected_id()
        self._tree.blockSignals(True)
        self._tree.clear()
        warned = {w.node_id for w in self._draft.warnings()}
        for node in self._draft.roots:
            self._tree.addTopLevelItem(self._build_item(node, warned))
        self._restore_expansion(expanded)
        self._tree.blockSignals(False)
        if selected:
            self.select_node(selected)

    def update_labels(self) -> None:
        """Refresh every row's text after field edits, without rebuilding."""
        warned = {w.node_id for w in self._draft.warnings()}
        for item in self._all_items():
            node = self._draft.find(item.data(_COL_LABEL, _ROLE_ID))
            if node is not None:
                item.setText(_COL_LABEL, self._label(node, warned))

    def select_node(self, node_id: str) -> None:
        """Select and reveal the row for a node id, if it exists."""
        for item in self._all_items():
            if item.data(_COL_LABEL, _ROLE_ID) == node_id:
                self._tree.setCurrentItem(item)
                self._tree.scrollToItem(item)
                return

    def selected_id(self) -> str:
        item = self._tree.currentItem()
        return item.data(_COL_LABEL, _ROLE_ID) if item is not None else ""

    def _build_item(self, node, warned: set[str]) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        item.setText(_COL_LABEL, self._label(node, warned))
        item.setData(_COL_LABEL, _ROLE_ID, node.id)
        is_container = isinstance(node, ContainerDraft)
        if is_container:
            font = item.font(_COL_LABEL)
            font.setBold(True)
            item.setFont(_COL_LABEL, font)
            for child in node.children:
                item.addChild(self._build_item(child, warned))
        self._tree.setItemWidget(
            item, _COL_ACTIONS, self._actions(node.id, is_container)
        )
        item.setExpanded(True)
        return item

    def _label(self, node, warned: set[str]) -> str:
        if isinstance(node, ContainerDraft):
            teams, people = self._draft.rollup(node.id)
            badge = f"{teams} teams · {people:,} people"
            warning = _WARNING_BADGE if node.id in warned else ""
            return f"{node.category} · {node.name}   ({badge}){warning}"
        return f"{node.name}   ({node.people:,} people)"

    def _actions(self, node_id: str, is_container: bool) -> QWidget:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(ui_scale.px(_ACTION_SPACING))
        if is_container:
            add = action_button("+", "Add a team or a sub-group here")
            add.clicked.connect(lambda _=False, i=node_id: self._add_menu(i))
            column.addWidget(add)
        remove = action_button("-", "Remove this item")
        remove.clicked.connect(lambda _=False, i=node_id: self._remove(i))
        column.addWidget(remove)
        return holder

    # ------------------------------------------------------------ operations

    def _add_root_group(self) -> None:
        node = self._draft.add_container(None)
        self._after_change(node.id)

    def _add_menu(self, node_id: str) -> None:
        menu = QMenu(self)
        menu.addAction(_ADD_TEAM_TEXT, lambda: self._add_team(node_id))
        menu.addAction(_ADD_SUBGROUP_TEXT, lambda: self._add_subgroup(node_id))
        menu.exec(QCursor.pos())

    def _add_team(self, parent_id: str) -> None:
        node = self._draft.add_team(parent_id)
        self._after_change(node.id)

    def _add_subgroup(self, parent_id: str) -> None:
        node = self._draft.add_container(parent_id)
        self._after_change(node.id)

    def _remove(self, node_id: str) -> None:
        summary = self._draft.removal_summary(node_id)
        if summary.is_container and summary.team_count:
            message = (
                f"Remove {summary.name} and its {summary.team_count} teams, "
                f"{summary.people:,} people?"
            )
        elif summary.is_container:
            message = f"Remove the group '{summary.name}'?"
        else:
            message = f"Remove the team '{summary.name}'?"
        answer = QMessageBox.question(
            self,
            "Remove",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._draft.remove(node_id)
        self._after_change("")

    def _move_up(self, node_id: str) -> None:
        if self._draft.move_up(node_id):
            self._after_change(node_id)

    def _move_down(self, node_id: str) -> None:
        if self._draft.move_down(node_id):
            self._after_change(node_id)

    def _move_to(self, node_id: str) -> None:
        targets = self._draft.move_targets(node_id)
        labels = [_TOP_LEVEL_LABEL, *(label for _, label in targets)]
        choice, accepted = QInputDialog.getItem(
            self, "Move to", "Move into:", labels, 0, False
        )
        if not accepted:
            return
        parent_id = None
        for ident, label in targets:
            if label == choice:
                parent_id = ident
        if self._draft.move_to(node_id, parent_id):
            self._after_change(node_id)

    def _duplicate(self, node_id: str) -> None:
        copy = self._draft.duplicate(node_id)
        self._after_change(copy.id)

    def _context_menu(self, position) -> None:
        item = self._tree.itemAt(position)
        if item is None:
            return
        node_id = item.data(_COL_LABEL, _ROLE_ID)
        node = self._draft.find(node_id)
        menu = QMenu(self)
        if isinstance(node, ContainerDraft):
            menu.addAction(_ADD_TEAM_TEXT, lambda: self._add_team(node_id))
            menu.addAction(_ADD_SUBGROUP_TEXT, lambda: self._add_subgroup(node_id))
            menu.addSeparator()
        menu.addAction("Duplicate", lambda: self._duplicate(node_id))
        menu.addAction("Move up", lambda: self._move_up(node_id))
        menu.addAction("Move down", lambda: self._move_down(node_id))
        menu.addAction("Move to...", lambda: self._move_to(node_id))
        menu.addSeparator()
        menu.addAction("Remove", lambda: self._remove(node_id))
        menu.exec(self._tree.viewport().mapToGlobal(position))

    def _after_change(self, select_id: str) -> None:
        self.rebuild()
        if select_id:
            self.select_node(select_id)
        self.structureChanged.emit()

    # --------------------------------------------------------------- helpers

    def _selection_changed(self) -> None:
        self.nodeSelected.emit(self.selected_id())

    def _all_items(self):
        def visit(item):
            yield item
            for index in range(item.childCount()):
                yield from visit(item.child(index))

        for index in range(self._tree.topLevelItemCount()):
            yield from visit(self._tree.topLevelItem(index))

    def _expanded_ids(self) -> set[str]:
        return {
            item.data(_COL_LABEL, _ROLE_ID)
            for item in self._all_items()
            if item.isExpanded()
        }

    def _restore_expansion(self, expanded: set[str]) -> None:
        if not expanded:
            return
        for item in self._all_items():
            item.setExpanded(item.data(_COL_LABEL, _ROLE_ID) in expanded)
