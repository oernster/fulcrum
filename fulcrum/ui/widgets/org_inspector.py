"""The org editor's right pane: the inspector for the selected node.

A container shows category, name and lead; a team shows name, people, whether
it ships without asking, its incentive skew and its owner. Fields write
straight through to the draft node and emit nodeEdited so the tree and footer
refresh. Name fields select their whole value on focus and carry a dice button
that rerolls from the shared name pool.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.glossary import (
    TERM_INCENTIVE_SKEW,
    TERM_LOCAL_AUTHORITY,
    short_help,
)
from fulcrum.application.org_draft import OrgDraft
from fulcrum.application.org_draft_nodes import ContainerDraft, TeamDraft
from fulcrum.domain.models import GROUP_CATEGORIES
from fulcrum.ui.widgets.org_editor_widgets import SelectAllLineEdit, dice_button

_MAX_SKEW_PERCENT = 100
_MAX_HEADCOUNT = 1_000_000
_PAGE_EMPTY = 0
_PAGE_CONTAINER = 1
_PAGE_TEAM = 2
_PLACEHOLDER = "Select an item in the tree to edit it here."
_CATEGORY_TIP = "The kind of group: pick a tier or type your own"
_LEAD_TIP = "The senior person this group's recommendations go to"
_OWNER_TIP = "The person who owns this team"
_PEOPLE_TIP = "How many people are in this team"


def _person_row(field: SelectAllLineEdit, dice) -> QWidget:
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(field, 1)
    row.addWidget(dice)
    return holder


class OrgInspectorPane(QWidget):
    """Edits the currently selected draft node's fields in place."""

    nodeEdited = Signal(str)

    def __init__(self, draft: OrgDraft, parent=None) -> None:
        super().__init__(parent)
        self._draft = draft
        self._node = None
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_empty_page())
        self._stack.addWidget(self._build_container_page())
        self._stack.addWidget(self._build_team_page())
        layout.addWidget(self._stack)
        layout.addStretch()

    # ----------------------------------------------------------------- pages

    def _build_empty_page(self) -> QWidget:
        page = QWidget()
        column = QVBoxLayout(page)
        hint = QLabel(_PLACEHOLDER)
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        column.addWidget(hint)
        column.addStretch()
        return page

    def _build_container_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._category = QComboBox()
        self._category.setEditable(True)
        self._category.addItems(GROUP_CATEGORIES)
        self._category.setToolTip(_CATEGORY_TIP)
        self._category.currentTextChanged.connect(self._apply_category)
        form.addRow("Category", self._category)
        self._container_name = SelectAllLineEdit()
        self._container_name.textChanged.connect(self._apply_name)
        form.addRow("Name", self._container_name)
        self._lead = SelectAllLineEdit()
        self._lead.setToolTip(_LEAD_TIP)
        self._lead.textChanged.connect(self._apply_lead)
        lead_dice = dice_button()
        lead_dice.clicked.connect(lambda: self._reroll(self._lead))
        form.addRow("Lead", _person_row(self._lead, lead_dice))
        return page

    def _build_team_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._team_name = SelectAllLineEdit()
        self._team_name.textChanged.connect(self._apply_name)
        form.addRow("Name", self._team_name)
        self._people = QSpinBox()
        self._people.setRange(1, _MAX_HEADCOUNT)
        self._people.setGroupSeparatorShown(True)
        self._people.setToolTip(_PEOPLE_TIP)
        self._people.valueChanged.connect(self._apply_people)
        form.addRow("People", self._people)
        self._ships = QCheckBox("Ships without asking")
        self._ships.setToolTip(short_help(TERM_LOCAL_AUTHORITY))
        self._ships.toggled.connect(self._apply_ships)
        form.addRow("", self._ships)
        self._skew = QSpinBox()
        self._skew.setRange(0, _MAX_SKEW_PERCENT)
        self._skew.setToolTip(short_help(TERM_INCENTIVE_SKEW))
        self._skew.valueChanged.connect(self._apply_skew)
        skew_label = QLabel("Incentive skew %")
        skew_label.setToolTip(short_help(TERM_INCENTIVE_SKEW))
        form.addRow(skew_label, self._skew)
        self._owner = SelectAllLineEdit()
        self._owner.setToolTip(_OWNER_TIP)
        self._owner.textChanged.connect(self._apply_owner)
        owner_dice = dice_button()
        owner_dice.clicked.connect(lambda: self._reroll(self._owner))
        form.addRow("Owner", _person_row(self._owner, owner_dice))
        return page

    # ------------------------------------------------------------- selection

    def set_node(self, node_id: str) -> None:
        """Show the editor page for a node id, or the placeholder for ''."""
        self._node = self._draft.find(node_id) if node_id else None
        self._loading = True
        if isinstance(self._node, ContainerDraft):
            self._category.setCurrentText(self._node.category)
            self._container_name.setText(self._node.name)
            self._lead.setText(self._node.lead)
            self._stack.setCurrentIndex(_PAGE_CONTAINER)
        elif isinstance(self._node, TeamDraft):
            self._team_name.setText(self._node.name)
            self._people.setValue(self._node.people)
            self._ships.setChecked(self._node.ships_without_asking)
            self._skew.setValue(self._node.skew_percent)
            self._owner.setText(self._node.owner)
            self._stack.setCurrentIndex(_PAGE_TEAM)
        else:
            self._stack.setCurrentIndex(_PAGE_EMPTY)
        self._loading = False

    # ---------------------------------------------------------------- writes

    def _edited(self) -> None:
        if not self._loading and self._node is not None:
            self.nodeEdited.emit(self._node.id)

    def _apply_category(self, text: str) -> None:
        if isinstance(self._node, ContainerDraft):
            self._node.category = text.strip()
            self._edited()

    def _apply_name(self, text: str) -> None:
        if self._node is not None:
            self._node.name = text.strip()
            self._edited()

    def _apply_lead(self, text: str) -> None:
        if isinstance(self._node, ContainerDraft):
            self._node.lead = text.strip()
            self._edited()

    def _apply_people(self, value: int) -> None:
        if isinstance(self._node, TeamDraft):
            self._node.people = value
            self._edited()

    def _apply_ships(self, checked: bool) -> None:
        if isinstance(self._node, TeamDraft):
            self._node.ships_without_asking = checked
            self._edited()

    def _apply_skew(self, value: int) -> None:
        if isinstance(self._node, TeamDraft):
            self._node.skew_percent = value
            self._edited()

    def _apply_owner(self, text: str) -> None:
        if isinstance(self._node, TeamDraft):
            self._node.owner = text.strip()
            self._edited()

    def _reroll(self, field: SelectAllLineEdit) -> None:
        field.setText(self._draft.reroll_name(field.text().strip()))
