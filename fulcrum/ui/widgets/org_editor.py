"""The scalable 'Model my organisation' editor.

A tree holds the recursive structure: domains nest under domains to any depth,
and teams are leaves under a domain. Each team carries its authority and
incentive skew inline; each domain carries its lead. Structure is edited in
place: a domain row carries a + (add a team or a sub-domain here) and every row
carries a - (remove, behind a confirm), so where a change lands is explicit
rather than tied to the current selection. The editor produces an OrgBlueprint,
which the application layer validates into an OrgState. Very large orgs are
better imported as JSON; this is the hand-built and tweak path.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.dto import DomainSpec, OrgBlueprint, TeamSpec
from fulcrum.domain.models import DEFAULT_CATEGORY, DEFAULT_HEADCOUNT, GROUP_CATEGORIES
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.dependency_editor import DependencyEditor
from fulcrum.ui.widgets.glossary_dialog import GlossaryDialog
from fulcrum.ui.widgets.org_editor_widgets import (
    action_button,
    centered,
    default_category,
    labelled,
)

_KIND_DOMAIN = "domain"
_KIND_TEAM = "team"
_ROLE_KIND = int(Qt.ItemDataRole.UserRole)
_ROLE_ID = int(Qt.ItemDataRole.UserRole) + 1

_COL_NAME = 0
_COL_AUTHORITY = 1
_COL_SKEW = 2
_COL_PEOPLE = 3
_COL_LEAD = 4
_COL_ACTIONS = 5
_HEADERS = (
    "Name",
    "Ships without asking",
    "Incentive skew %",
    "People",
    "Lead / owner",
    "",
)

_ACCENT = "#f59e0b"
_ADD_TEAM_TEXT = "Add team here"
_ADD_SUBDOMAIN_TEXT = "Add a sub-group here"
_ADD_GLYPH = "+"
_REMOVE_GLYPH = "-"
_ACTION_SPACING = 2
_LEAD_COLUMN_WIDTH = 168
_CATEGORY_WIDTH = 124
_CATEGORY_SPACING = 6
_AUTHORITY_TIP = "Tick if the team can decide and ship on its own, without escalating."
_SKEW_TIP = (
    "How far the team's local incentives pull against the system outcome. "
    "High skew shows up later as rework."
)

_MAX_SKEW_PERCENT = 100
_DEFAULT_SKEW_PERCENT = 30
_MAX_HEADCOUNT = 1_000_000
_MIN_WORKLOAD = 1
_MAX_WORKLOAD = 50
_DEFAULT_WORKLOAD = 6
_MIN_WIDTH = 840
_MIN_HEIGHT = 640
_HINT = (
    "Build your organisation: start a group and pick its category (Division, "
    "Department, Domain, ...), then use + on a group to add a team or a "
    "sub-group; use - to remove an item. Groups nest to any depth. Tick the "
    "teams that ship without escalating. Very large orgs are quicker to import "
    "as JSON. Unsure on a term like incentive skew? Open the "
    f'<a href="#glossary" style="color: {_ACCENT};">decision glossary</a>.'
)


class OrgEditorDialog(QDialog):
    """Collects a hierarchical OrgBlueprint: domains, teams, dependencies."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Model my organisation")
        self.setMinimumSize(ui_scale.px(_MIN_WIDTH), ui_scale.px(_MIN_HEIGHT))
        self._id_seq = 0
        self._domain_count = 0
        self._team_count = 0

        layout = QVBoxLayout(self)
        hint = QLabel(_HINT)
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        hint.setOpenExternalLinks(False)
        hint.linkActivated.connect(self._open_glossary)
        layout.addWidget(hint)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(len(_HEADERS))
        self._tree.setHeaderLabels(list(_HEADERS))
        header = self._tree.header()
        header.setSectionResizeMode(_COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            _COL_AUTHORITY, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(_COL_SKEW, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            _COL_PEOPLE, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(_COL_LEAD, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(
            _COL_ACTIONS, QHeaderView.ResizeMode.ResizeToContents
        )
        # The actions column is fixed to its buttons; without this the last
        # section stretches and steals the leftover width, starving the Name
        # column so the name editors clip. Let Name absorb the remaining width.
        header.setStretchLastSection(False)
        self._tree.setColumnWidth(_COL_LEAD, ui_scale.px(_LEAD_COLUMN_WIDTH))
        header_item = self._tree.headerItem()
        header_item.setToolTip(_COL_AUTHORITY, _AUTHORITY_TIP)
        header_item.setToolTip(_COL_SKEW, _SKEW_TIP)
        layout.addWidget(self._tree, 1)
        layout.addLayout(self._build_buttons())

        layout.addWidget(labelled(QLabel("Dependencies between teams")))
        self._deps = DependencyEditor()
        layout.addWidget(self._deps)

        workload_row = QHBoxLayout()
        workload_row.addWidget(QLabel("Decisions arriving per team each turn"))
        self._workload = QSpinBox()
        self._workload.setRange(_MIN_WORKLOAD, _MAX_WORKLOAD)
        self._workload.setValue(_DEFAULT_WORKLOAD)
        workload_row.addWidget(self._workload)
        workload_row.addStretch()
        layout.addLayout(workload_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._seed()

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        add_domain = QPushButton("Add a group")
        add_domain.setToolTip("Start a new top-level group")
        add_domain.clicked.connect(self._add_root_domain)
        row.addWidget(add_domain)
        row.addStretch()
        return row

    def _seed(self) -> None:
        domain = self._add_root_domain()
        self._add_team_under(domain)
        self._sync_teams()

    def _new_id(self, prefix: str) -> str:
        self._id_seq += 1
        return f"{prefix}_{self._id_seq}"

    def _add_root_domain(self) -> QTreeWidgetItem:
        return self._new_domain_item(None)

    def _add_team_under(self, domain_item: QTreeWidgetItem) -> None:
        self._team_count += 1
        item = QTreeWidgetItem(domain_item)
        item.setData(_COL_NAME, _ROLE_KIND, _KIND_TEAM)
        item.setData(_COL_NAME, _ROLE_ID, self._new_id("team"))
        self._tree.setItemWidget(item, _COL_NAME, QLineEdit(f"Team {self._team_count}"))
        self._tree.setItemWidget(item, _COL_AUTHORITY, centered(QCheckBox()))
        skew = QSpinBox()
        skew.setRange(0, _MAX_SKEW_PERCENT)
        skew.setValue(_DEFAULT_SKEW_PERCENT)
        self._tree.setItemWidget(item, _COL_SKEW, skew)
        people = QSpinBox()
        people.setRange(1, _MAX_HEADCOUNT)
        people.setGroupSeparatorShown(True)
        people.setValue(DEFAULT_HEADCOUNT)
        self._tree.setItemWidget(item, _COL_PEOPLE, people)
        owner = QLineEdit()
        owner.setPlaceholderText("owner (optional)")
        self._tree.setItemWidget(item, _COL_LEAD, owner)
        self._tree.setItemWidget(item, _COL_ACTIONS, self._actions(item, _KIND_TEAM))

    def _new_domain_item(self, parent: QTreeWidgetItem | None) -> QTreeWidgetItem:
        self._domain_count += 1
        item = QTreeWidgetItem(parent) if parent is not None else QTreeWidgetItem()
        if parent is None:
            self._tree.addTopLevelItem(item)
        item.setData(_COL_NAME, _ROLE_KIND, _KIND_DOMAIN)
        item.setData(_COL_NAME, _ROLE_ID, self._new_id("domain"))
        self._tree.setItemWidget(item, _COL_NAME, self._domain_name_cell(parent))
        lead = QLineEdit()
        lead.setPlaceholderText("lead (optional)")
        self._tree.setItemWidget(item, _COL_LEAD, lead)
        self._tree.setItemWidget(item, _COL_ACTIONS, self._actions(item, _KIND_DOMAIN))
        item.setExpanded(True)
        return item

    def _domain_name_cell(self, parent: QTreeWidgetItem | None) -> QWidget:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(ui_scale.px(_CATEGORY_SPACING))
        default = default_category(parent)
        category = QComboBox()
        category.setObjectName("GroupCategory")
        category.setEditable(True)
        category.addItems(GROUP_CATEGORIES)
        category.setCurrentText(default)
        category.setFixedWidth(ui_scale.px(_CATEGORY_WIDTH))
        category.setToolTip("The kind of group: pick a tier or type your own")
        row.addWidget(category)
        name = QLineEdit(f"{default} {self._domain_count}")
        name.setObjectName("GroupName")
        row.addWidget(name)
        return holder

    def _actions(self, item: QTreeWidgetItem, kind: str) -> QWidget:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(ui_scale.px(_ACTION_SPACING))
        if kind == _KIND_DOMAIN:
            add = action_button(_ADD_GLYPH, "Add a team or a sub-group here")
            add.clicked.connect(lambda _=False, it=item: self._show_add_menu(it))
            column.addWidget(add)
        remove = action_button(_REMOVE_GLYPH, "Remove this item")
        remove.clicked.connect(lambda _=False, it=item: self._remove_item(it))
        column.addWidget(remove)
        return holder

    def _open_glossary(self) -> None:
        GlossaryDialog(self).exec()

    def _show_add_menu(self, domain_item: QTreeWidgetItem) -> None:
        menu = QMenu(self)
        menu.addAction(_ADD_TEAM_TEXT, lambda: self._add_team_to(domain_item))
        menu.addAction(_ADD_SUBDOMAIN_TEXT, lambda: self._add_subdomain_to(domain_item))
        menu.exec(QCursor.pos())

    def _add_team_to(self, domain_item: QTreeWidgetItem) -> None:
        self._add_team_under(domain_item)
        domain_item.setExpanded(True)
        self._sync_teams()

    def _add_subdomain_to(self, domain_item: QTreeWidgetItem) -> None:
        self._new_domain_item(domain_item)
        domain_item.setExpanded(True)

    def _remove_item(self, item: QTreeWidgetItem) -> None:
        if not self._confirm_remove(item):
            return
        parent = item.parent()
        if parent is not None:
            parent.removeChild(item)
        else:
            index = self._tree.indexOfTopLevelItem(item)
            self._tree.takeTopLevelItem(index)
        self._sync_teams()

    def _confirm_remove(self, item: QTreeWidgetItem) -> bool:
        kind = item.data(_COL_NAME, _ROLE_KIND)
        name = self._name_of(item) or "this item"
        if kind == _KIND_DOMAIN and item.childCount() > 0:
            message = (
                f"Remove the domain '{name}' and everything inside it? Its "
                "sub-domains and teams will be removed too."
            )
        elif kind == _KIND_DOMAIN:
            message = f"Remove the domain '{name}'?"
        else:
            message = f"Remove the team '{name}'?"
        answer = QMessageBox.question(
            self,
            "Remove",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _sync_teams(self) -> None:
        self._deps.set_teams(self._current_teams())

    def _current_teams(self) -> list[tuple[str, str]]:
        teams = []
        for item, _ in self._walk():
            if item.data(_COL_NAME, _ROLE_KIND) == _KIND_TEAM:
                teams.append((self._id_of(item), self._name_of(item)))
        return teams

    def _walk(self):
        def visit(item, parent):
            yield item, parent
            for index in range(item.childCount()):
                yield from visit(item.child(index), item)

        for index in range(self._tree.topLevelItemCount()):
            yield from visit(self._tree.topLevelItem(index), None)

    def _id_of(self, item: QTreeWidgetItem) -> str:
        return item.data(_COL_NAME, _ROLE_ID)

    def _text(self, item: QTreeWidgetItem, column: int) -> str:
        widget = self._tree.itemWidget(item, column)
        return widget.text().strip() if widget is not None else ""

    def _name_of(self, item: QTreeWidgetItem) -> str:
        widget = self._tree.itemWidget(item, _COL_NAME)
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        edit = widget.findChild(QLineEdit, "GroupName") if widget is not None else None
        return edit.text().strip() if edit is not None else ""

    def _category_of(self, item: QTreeWidgetItem) -> str:
        widget = self._tree.itemWidget(item, _COL_NAME)
        combo = (
            widget.findChild(QComboBox, "GroupCategory") if widget is not None else None
        )
        return combo.currentText().strip() if combo is not None else DEFAULT_CATEGORY

    def _authority_of(self, item: QTreeWidgetItem) -> bool:
        holder = self._tree.itemWidget(item, _COL_AUTHORITY)
        checkbox = holder.findChild(QCheckBox) if holder is not None else None
        return checkbox.isChecked() if checkbox is not None else False

    def to_blueprint(self) -> OrgBlueprint:
        domains: list[DomainSpec] = []
        teams: list[TeamSpec] = []
        for item, parent in self._walk():
            ident = self._id_of(item)
            parent_id = self._id_of(parent) if parent is not None else None
            name = self._name_of(item) or ident
            if item.data(_COL_NAME, _ROLE_KIND) == _KIND_DOMAIN:
                domains.append(
                    DomainSpec(
                        ident,
                        name,
                        parent_id,
                        self._text(item, _COL_LEAD),
                        self._category_of(item),
                    )
                )
            else:
                teams.append(
                    TeamSpec(
                        ident,
                        name,
                        self._authority_of(item),
                        self._tree.itemWidget(item, _COL_SKEW).value()
                        / _MAX_SKEW_PERCENT,
                        parent_id,
                        owner=self._text(item, _COL_LEAD),
                        headcount=self._tree.itemWidget(item, _COL_PEOPLE).value(),
                    )
                )
        return OrgBlueprint(
            teams=tuple(teams),
            dependencies=self._deps.dependencies(),
            workload=self._workload.value(),
            domains=tuple(domains),
        )
