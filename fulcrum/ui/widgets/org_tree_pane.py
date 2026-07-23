"""The org editor's left pane: the organisation rendered as a live tree.

A new company is the outer cage (button or right-click on empty space); every
unit takes items with the inline + or the context menu and a new item starts
as a team, converted to any tier from the inspector's type dropdown. Rows can
be dragged file-manager style: onto a unit to move inside, between rows to
reorder, Ctrl held to copy. The pane is a thin view over the OrgDraft: every
operation calls the draft then rebuilds, so the tree always reflects the
model.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.org_draft import OrgDraft
from fulcrum.application.org_draft_nodes import ContainerDraft
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.org_editor_widgets import action_button
from fulcrum.ui.widgets.org_tree_dnd import DraftTree

_ROLE_ID = int(Qt.ItemDataRole.UserRole)
_COL_LABEL = 0
_COL_ACTIONS = 1
_ACTIONS_COLUMN_WIDTH = 92
_ACTION_SPACING = 4
# Vertical and trailing space around the +/- buttons so their 2px hover ring
# never clips against the row or viewport edge.
_ACTION_MARGIN = 4
_ACTION_RIGHT_PAD = 6
_WARNING_BADGE = " \N{WARNING SIGN}"
_TOP_LEVEL_LABEL = "(top level)"
_ADD_GLYPH = "+"
# A real minus sign: the ASCII hyphen renders as a tiny dash at button size.
_REMOVE_GLYPH = "\N{MINUS SIGN}"
_NEW_COMPANY_TEXT = "New company"
_ADD_ITEM_TEXT = "Add item here"
_DRAG_HINT = (
    "Drag an item onto a unit to move it inside, between rows to reorder; "
    "hold Ctrl to copy. A unit never sits under a lower tier and teams are "
    "always the leaves."
)


class OrgTreePane(QWidget):
    """Shows the draft as a tree and applies structural edits to it."""

    nodeSelected = Signal(str)
    structureChanged = Signal()

    def __init__(self, draft: OrgDraft, parent=None) -> None:
        super().__init__(parent)
        self._draft = draft
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tree = DraftTree(
            self._draft.can_place, self._handle_drop, self._is_container
        )
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
        new_company = QPushButton(_NEW_COMPANY_TEXT)
        new_company.setToolTip("Start a new top-level company")
        new_company.clicked.connect(self._new_company)
        expand = QPushButton("Expand all")
        expand.clicked.connect(self._tree.expandAll)
        collapse = QPushButton("Collapse all")
        collapse.clicked.connect(self._tree.collapseAll)
        row.addWidget(new_company)
        row.addWidget(expand)
        row.addWidget(collapse)
        row.addStretch()
        layout.addLayout(row)

        hint = QLabel(_DRAG_HINT)
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.rebuild()

    # ------------------------------------------------------------- rendering

    def rebuild(self) -> None:
        """Re-render the whole tree, preserving expansion and selection."""
        had_items = self._tree.topLevelItemCount() > 0
        expanded = self._expanded_ids()
        selected = self.selected_id()
        self._tree.blockSignals(True)
        self._tree.clear()
        warned = self._warnings_by_id()
        for node in self._draft.roots:
            self._add_row(node, None, warned)
        if had_items:
            self._restore_expansion(expanded)
        self._tree.blockSignals(False)
        if selected:
            self.select_node(selected)

    def update_labels(self) -> None:
        """Refresh every row's text after field edits, without rebuilding."""
        warned = self._warnings_by_id()
        for item in self._all_items():
            node = self._draft.find(item.data(_COL_LABEL, _ROLE_ID))
            if node is not None:
                item.setText(_COL_LABEL, self._label(node, warned))
                item.setToolTip(_COL_LABEL, warned.get(node.id, ""))

    def _warnings_by_id(self) -> dict[str, str]:
        return {w.node_id: w.message for w in self._draft.warnings()}

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

    def _add_row(self, node, parent_item, warned: dict[str, str]) -> None:
        item = QTreeWidgetItem()
        item.setText(_COL_LABEL, self._label(node, warned))
        item.setToolTip(_COL_LABEL, warned.get(node.id, ""))
        item.setData(_COL_LABEL, _ROLE_ID, node.id)
        is_container = isinstance(node, ContainerDraft)
        if is_container:
            font = item.font(_COL_LABEL)
            font.setBold(True)
            item.setFont(_COL_LABEL, font)
        actions = self._actions(node.id, is_container)
        # The row must never be shorter than the action buttons: an overlaid
        # item widget is clipped to the row rect, and a too-short row slices
        # the bottom border off the buttons' ring. The explicit size hint
        # forces the row to fit the holder at any UI scale.
        item.setSizeHint(_COL_ACTIONS, actions.sizeHint())
        # Attach before decorating: item widgets and expansion state are view
        # state, which Qt silently drops on rows not yet in the tree.
        if parent_item is None:
            self._tree.addTopLevelItem(item)
        else:
            parent_item.addChild(item)
        self._tree.setItemWidget(item, _COL_ACTIONS, actions)
        if is_container:
            for child in node.children:
                self._add_row(child, item, warned)
        item.setExpanded(True)

    def _label(self, node, warned: dict[str, str]) -> str:
        if isinstance(node, ContainerDraft):
            teams, people = self._draft.rollup(node.id)
            badge = f"{teams} teams · {people:,} people"
            warning = _WARNING_BADGE if node.id in warned else ""
            return f"{node.category} · {node.name}   ({badge}){warning}"
        return f"{node.name}   ({node.people:,} people)"

    def _actions(self, node_id: str, is_container: bool) -> QWidget:
        # + and - sit side by side so a row only needs one button of height;
        # a team has no +, so a stretch keeps every - aligned in its own
        # column under the others. The holder is named so the stylesheet can
        # keep it transparent over the tree surface.
        holder = QWidget()
        holder.setObjectName("TreeActionCell")
        row = QHBoxLayout(holder)
        margin = ui_scale.px(_ACTION_MARGIN)
        row.setContentsMargins(0, margin, ui_scale.px(_ACTION_RIGHT_PAD), margin)
        row.setSpacing(ui_scale.px(_ACTION_SPACING))
        if is_container:
            add = action_button(_ADD_GLYPH, _ADD_ITEM_TEXT)
            add.clicked.connect(lambda _=False, i=node_id: self._add_item(i))
            row.addWidget(add)
        else:
            row.addStretch()
        remove = action_button(_REMOVE_GLYPH, "Remove this item")
        remove.clicked.connect(lambda _=False, i=node_id: self._remove(i))
        row.addWidget(remove)
        return holder

    # ------------------------------------------------------------ operations

    def _new_company(self) -> None:
        node = self._draft.add_container(None)
        self._after_change(node.id)

    def _add_item(self, parent_id: str) -> None:
        node = self._draft.add_team(parent_id)
        self._after_change(node.id)

    def _remove(self, node_id: str) -> None:
        summary = self._draft.removal_summary(node_id)
        if summary.is_container and summary.team_count:
            message = (
                f"Remove {summary.name} and its {summary.team_count} teams, "
                f"{summary.people:,} people?"
            )
        elif summary.is_container:
            message = f"Remove the unit '{summary.name}'?"
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

    def _is_container(self, node_id: str) -> bool:
        return isinstance(self._draft.find(node_id), ContainerDraft)

    def _handle_drop(
        self, node_id: str, parent_id: str | None, index, copy: bool
    ) -> None:
        if copy:
            node = self._draft.copy_into(node_id, parent_id, index)
            if node is not None:
                self._after_change(node.id)
        elif self._draft.move_to(node_id, parent_id, index):
            self._after_change(node_id)

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
        menu = QMenu(self)
        if item is None:
            menu.addAction(_NEW_COMPANY_TEXT, self._new_company)
            menu.exec(self._tree.viewport().mapToGlobal(position))
            return
        node_id = item.data(_COL_LABEL, _ROLE_ID)
        node = self._draft.find(node_id)
        if isinstance(node, ContainerDraft):
            menu.addAction(_ADD_ITEM_TEXT, lambda: self._add_item(node_id))
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
        for item in self._all_items():
            item.setExpanded(item.data(_COL_LABEL, _ROLE_ID) in expanded)
