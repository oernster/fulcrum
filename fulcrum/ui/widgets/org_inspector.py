"""The org editor's right pane: the inspector for the selected node.

Every item leads with a Type dropdown: the group tiers (or a custom label)
plus Team. Picking a different type converts the item in place, so an added
item (born a team) becomes a Division, Department or anything else in one
motion; a unit still holding items refuses to become a team and a tier never
supersedes its parent. The remaining fields write straight through to the
draft node. Name fields select their whole value on focus and carry a dice
button that rerolls from the shared name pool.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
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
from fulcrum.application.org_draft_nodes import TEAM_TYPE, ContainerDraft, TeamDraft
from fulcrum.domain.models import GROUP_CATEGORIES
from fulcrum.ui.widgets.org_editor_widgets import (
    ClickOpenComboBox,
    SelectAllLineEdit,
    dice_button,
)

_MAX_SKEW_PERCENT = 100
_MAX_HEADCOUNT = 1_000_000
_PAGE_EMPTY = 0
_PAGE_CONTAINER = 1
_PAGE_TEAM = 2
_PLACEHOLDER = "Select an item in the tree to edit it here."
_TYPE_TIP = (
    "What this item is: a tier such as Division, your own label or Team. "
    "Changing it converts the item in place."
)
_LEAD_TIP = "The senior person this unit's recommendations go to"
_OWNER_TIP = "The person who owns this team"
_PEOPLE_TIP = "How many people are in this team"
_STILL_HOLDS_ITEMS = (
    "This unit still holds items, so it cannot become a team. Move or "
    "remove what is inside it first."
)
_TIER_TOO_HIGH = (
    "That tier would sit above this item's parent. Move the item to the top "
    "level (or under a higher tier) first."
)


def _person_row(field: SelectAllLineEdit, dice) -> QWidget:
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(field, 1)
    row.addWidget(dice)
    return holder


def _type_combo() -> QComboBox:
    combo = ClickOpenComboBox()
    combo.addItems([*GROUP_CATEGORIES, TEAM_TYPE])
    combo.setToolTip(_TYPE_TIP)
    return combo


class OrgInspectorPane(QWidget):
    """Edits the currently selected draft node's fields in place."""

    nodeEdited = Signal(str)
    kindChanged = Signal(str)

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
        self._container_type = _type_combo()
        self._wire_type(self._container_type)
        form.addRow("Type", self._container_type)
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
        self._team_type = _type_combo()
        self._wire_type(self._team_type)
        form.addRow("Type", self._team_type)
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

    def _wire_type(self, combo: QComboBox) -> None:
        # activated fires on dropdown picks and editingFinished on typed
        # labels, so a half-typed custom label never converts per keystroke.
        combo.activated.connect(lambda _index, c=combo: self._apply_type(c))
        combo.lineEdit().editingFinished.connect(lambda c=combo: self._apply_type(c))

    # ------------------------------------------------------------- selection

    def set_node(self, node_id: str) -> None:
        """Show the editor page for a node id, or the placeholder for ''."""
        self._node = self._draft.find(node_id) if node_id else None
        self._loading = True
        if isinstance(self._node, ContainerDraft):
            self._container_type.setCurrentText(self._node.category)
            self._container_name.setText(self._node.name)
            self._lead.setText(self._node.lead)
            self._stack.setCurrentIndex(_PAGE_CONTAINER)
        elif isinstance(self._node, TeamDraft):
            self._team_type.setCurrentText(TEAM_TYPE)
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

    def _apply_type(self, combo: QComboBox) -> None:
        if self._loading or self._node is None:
            return
        chosen = combo.currentText().strip()
        if not chosen:
            self._reset_type(combo)
            return
        if isinstance(self._node, TeamDraft):
            self._convert_team(chosen, combo)
        else:
            self._retype_container(chosen, combo)

    def _convert_team(self, chosen: str, combo: QComboBox) -> None:
        if chosen == TEAM_TYPE:
            return
        node_id = self._node.id
        if self._draft.convert_to_container(node_id, chosen) is None:
            QMessageBox.information(self, "Type", _TIER_TOO_HIGH)
            self._reset_type(combo)
            return
        self.kindChanged.emit(node_id)

    def _retype_container(self, chosen: str, combo: QComboBox) -> None:
        node_id = self._node.id
        if chosen == TEAM_TYPE:
            if self._draft.convert_to_team(node_id) is None:
                QMessageBox.information(self, "Type", _STILL_HOLDS_ITEMS)
                self._reset_type(combo)
                return
            self.kindChanged.emit(node_id)
            return
        if chosen == self._node.category:
            return
        if not self._draft.set_category(node_id, chosen):
            QMessageBox.information(self, "Type", _TIER_TOO_HIGH)
            self._reset_type(combo)
            return
        self._loading = True
        self._container_name.setText(self._node.name)
        self._loading = False
        self._edited()

    def _reset_type(self, combo: QComboBox) -> None:
        self._loading = True
        if isinstance(self._node, TeamDraft):
            combo.setCurrentText(TEAM_TYPE)
        else:
            combo.setCurrentText(self._node.category)
        self._loading = False

    def _edited(self) -> None:
        if not self._loading and self._node is not None:
            self.nodeEdited.emit(self._node.id)

    def _apply_name(self, text: str) -> None:
        if not self._loading and self._node is not None:
            self._node.name = text.strip()
            self._edited()

    def _apply_lead(self, text: str) -> None:
        if not self._loading and isinstance(self._node, ContainerDraft):
            self._node.lead = text.strip()
            self._edited()

    def _apply_people(self, value: int) -> None:
        if not self._loading and isinstance(self._node, TeamDraft):
            self._node.people = value
            self._edited()

    def _apply_ships(self, checked: bool) -> None:
        if not self._loading and isinstance(self._node, TeamDraft):
            self._node.ships_without_asking = checked
            self._edited()

    def _apply_skew(self, value: int) -> None:
        if not self._loading and isinstance(self._node, TeamDraft):
            self._node.skew_percent = value
            self._edited()

    def _apply_owner(self, text: str) -> None:
        if not self._loading and isinstance(self._node, TeamDraft):
            self._node.owner = text.strip()
            self._edited()

    def _reroll(self, field: SelectAllLineEdit) -> None:
        field.setText(self._draft.reroll_name(field.text().strip()))
