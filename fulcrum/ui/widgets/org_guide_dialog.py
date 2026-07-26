"""The hierarchy guide: a plan for every level of the organisation.

Two panes, like the org editor: the left pane is the org tree with each
frame's climb ("24.5 → 78.7") on its row, so the summit-versus-leaves
asymmetry is visible at a glance; the right pane is the selected frame's
move-by-move line with preview and play, as the old single-frame guide had.
Leaf lines carry the value and compose into the headline; an aggregate row
is the view from that altitude, shown but never composed.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.dto import MoveValuation
from fulcrum.application.interfaces import Simulator
from fulcrum.application.org_guide import GuideNode, OrgGuide
from fulcrum.application.planner import GuideStep
from fulcrum.ui import ui_scale
from fulcrum.ui.widgets.board_renderers import clear_layout, magnifier_button
from fulcrum.ui.widgets.move_preview_dialog import MovePreviewDialog
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog

_MIN_WIDTH = 980
_MIN_HEIGHT = 560
_TREE_SHARE = 2
_STEPS_SHARE = 3
_SCORE_DECIMALS = 1
_NODE_ROLE = Qt.ItemDataRole.UserRole
_GROW_TOGGLE_TEXT = "Allow the organisation to grow (split or add teams)"
_GROWTH_SAME_NOTE = "Growth does not improve any line from this position."
_HINT = "Up and Down move between moves; click a move or 🔍 to preview it."
_ALREADY_GOOD = (
    "This level is already in good shape; no single move improves it much " "from here."
)
_AGGREGATE_NOTE = (
    "The view from this altitude: its gains overlap the leaf lines beneath "
    "it, so only leaf lines count toward the headline."
)
_TOO_LARGE = "This section is too large to plan live; drill into its units."
_WIDGET = "widget"
_GROUP = "group"
_FORWARD = 1
_BACK = -1


def _step_text(index: int, step: GuideStep) -> str:
    return (
        f"{index + 1}. {step.move.display_label()}   "
        f"[{step.classification.value}]   "
        f"→ {step.score_after:.{_SCORE_DECIMALS}f}"
    )


def _climb(node: GuideNode) -> str:
    if not node.playable:
        return "too large"
    guide = node.guide
    if not guide.steps:
        return f"{guide.start_score:.{_SCORE_DECIMALS}f}"
    return (
        f"{guide.start_score:.{_SCORE_DECIMALS}f} → "
        f"{guide.final_score:.{_SCORE_DECIMALS}f}"
    )


def _same_lines(first: OrgGuide, second: OrgGuide) -> bool:
    def lines(tree: OrgGuide):
        return tuple(
            tuple((s.move.kind, s.move.targets) for s in node.guide.steps)
            for node in tree.leaf_nodes()
        )

    return lines(first) == lines(second)


class OrgGuideDialog(NeutralDialog):
    """Shows every frame's line, with the composed whole-org headline."""

    def __init__(
        self,
        guide: OrgGuide,
        growth_guide: OrgGuide,
        simulator: Simulator | None = None,
        on_play=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guide - path to a stronger org, level by level")
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setMinimumSize(ui_scale.px(_MIN_WIDTH), ui_scale.px(_MIN_HEIGHT))
        self._guide = guide
        self._growth_guide = growth_guide
        self._simulator = simulator
        self._on_play = on_play
        self._selected_frame: str | None = None

        layout = QVBoxLayout(self)
        heading = QLabel("Path to a stronger org, level by level")
        heading.setObjectName("Heading")
        layout.addWidget(heading)
        self._summary = QLabel("")
        self._summary.setObjectName("Muted")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)
        self._toggle = QCheckBox(_GROW_TOGGLE_TEXT)
        self._toggle.toggled.connect(self._render_current)
        layout.addWidget(self._toggle)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Level", "Line"])
        self._tree.setColumnWidth(0, ui_scale.px(280))
        self._tree.currentItemChanged.connect(lambda *_: self._render_steps())

        steps_box = QWidget()
        steps_layout = QVBoxLayout(steps_box)
        steps_layout.setContentsMargins(0, 0, 0, 0)
        self._frame_title = QLabel("")
        self._frame_title.setObjectName("Heading")
        steps_layout.addWidget(self._frame_title)
        self._frame_note = QLabel("")
        self._frame_note.setObjectName("Muted")
        self._frame_note.setWordWrap(True)
        steps_layout.addWidget(self._frame_note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._rows_holder = QWidget()
        self._rows = QVBoxLayout(self._rows_holder)
        scroll.setWidget(self._rows_holder)
        steps_layout.addWidget(scroll, 1)

        panes = QSplitter(Qt.Orientation.Horizontal)
        panes.addWidget(self._tree)
        panes.addWidget(steps_box)
        panes.setStretchFactor(0, _TREE_SHARE)
        panes.setStretchFactor(1, _STEPS_SHARE)
        layout.addWidget(panes, 1)

        row = QHBoxLayout()
        self._close_button = QPushButton("Close")
        self._close_button.clicked.connect(self.accept)
        row.addStretch()
        row.addWidget(self._close_button)
        layout.addLayout(row)

        self._render_current()
        QApplication.instance().installEventFilter(self)

    # ------------------------------------------------------------- rendering

    def _active(self) -> OrgGuide:
        return self._growth_guide if self._toggle.isChecked() else self._guide

    def _render_current(self) -> None:
        active = self._active()
        note = ""
        if self._toggle.isChecked() and _same_lines(self._guide, self._growth_guide):
            note = f"   {_GROWTH_SAME_NOTE}"
        self._summary.setText(
            "Whole organisation, playing every leaf line: "
            f"{active.flat_before:.{_SCORE_DECIMALS}f} → "
            f"{active.flat_after:.{_SCORE_DECIMALS}f}{note}"
        )
        self._rebuild_tree(active)

    def _rebuild_tree(self, active: OrgGuide) -> None:
        remembered = self._selected_frame
        self._tree.blockSignals(True)
        self._tree.clear()
        to_select: list[QTreeWidgetItem] = []

        def add(node: GuideNode, parent) -> None:
            label = node.label if not node.category else f"{node.label}"
            item = QTreeWidgetItem([label, _climb(node)])
            item.setData(0, _NODE_ROLE, node)
            if parent is None:
                self._tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            if node.frame_id == remembered:
                to_select.append(item)
            for child in node.children:
                add(child, item)

        for node in active.nodes:
            add(node, None)
        self._tree.expandAll()
        self._tree.blockSignals(False)
        if to_select:
            self._tree.setCurrentItem(to_select[0])
        else:
            self._tree.setCurrentItem(self._tree.topLevelItem(0))
        self._render_steps()

    def _current_node(self) -> GuideNode | None:
        item = self._tree.currentItem()
        if item is None:
            return None
        return item.data(0, _NODE_ROLE)

    def _render_steps(self) -> None:
        node = self._current_node()
        clear_layout(self._rows)
        if node is None:
            return
        self._selected_frame = node.frame_id
        title = node.label if not node.category else f"{node.category}: {node.label}"
        self._frame_title.setText(f"{title}   {_climb(node)}")
        self._frame_note.setText("" if node.is_leaf else _AGGREGATE_NOTE)
        self._frame_note.setVisible(not node.is_leaf)
        if not node.playable:
            self._add_note(_TOO_LARGE)
            return
        if not node.guide.steps:
            self._add_note(_ALREADY_GOOD)
            return
        hint = QLabel(_HINT)
        hint.setObjectName("Muted")
        self._rows.addWidget(hint)
        for index, step in enumerate(node.guide.steps):
            self._rows.addWidget(self._step_row(node, index, step))
        self._rows.addStretch()

    def _add_note(self, text: str) -> None:
        note = QLabel(text)
        note.setObjectName("Muted")
        note.setWordWrap(True)
        self._rows.addWidget(note)
        self._rows.addStretch()

    def _step_row(self, node: GuideNode, index: int, step: GuideStep) -> QWidget:
        move = QPushButton(_step_text(index, step))
        move.setObjectName("MoveButton")
        move.setCursor(Qt.CursorShape.PointingHandCursor)
        move.clicked.connect(lambda _=False, n=node, s=step: self._preview(n, s))
        magnifier = magnifier_button(lambda n=node, s=step: self._preview(n, s))
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(move, 1)
        row.addWidget(magnifier)
        holder = QWidget()
        holder.setLayout(row)
        return holder

    def _preview(self, node: GuideNode, step: GuideStep) -> None:
        if self._simulator is None:
            return
        valuation = MoveValuation(
            step.move, step.score_before, step.score_after, step.classification
        )
        dialog = MovePreviewDialog(
            step.org_before, None, valuation, self._simulator, step.org_before, self
        )
        if dialog.exec() and self._on_play is not None:
            guides = self._on_play(step.move, node.frame_id)
            if guides is not None:
                self._guide, self._growth_guide = guides
                self._render_current()

    # ------------------------------------------------------------- keyboard

    # Focus ring: grow toggle -> tree -> moves group -> Close -> wrap. Tab and
    # Right step forward; Shift+Tab and Left step back. Up and Down stay with
    # the tree when it has focus and walk the move rows when they do.
    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        if QApplication.activeModalWidget() is not self:
            return False
        key = event.key()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if key == Qt.Key.Key_Right or (key == Qt.Key.Key_Tab and not shift):
            self._step(_FORWARD)
            return True
        if key in (Qt.Key.Key_Backtab, Qt.Key.Key_Left) or (
            key == Qt.Key.Key_Tab and shift
        ):
            self._step(_BACK)
            return True
        focus = QApplication.focusWidget()
        if key == Qt.Key.Key_Down:
            return self._step_within(focus, _FORWARD)
        if key == Qt.Key.Key_Up:
            return self._step_within(focus, _BACK)
        return False

    def done(self, result: int) -> None:
        QApplication.instance().removeEventFilter(self)
        super().done(result)

    def _ring(self) -> list:
        return [
            (_WIDGET, self._toggle),
            (_WIDGET, self._tree),
            (_GROUP, self._rows_holder),
            (_WIDGET, self._close_button),
        ]

    def _focusables(self) -> list:
        return [
            widget
            for widget in self._rows_holder.findChildren(QWidget)
            if widget.focusPolicy() != Qt.FocusPolicy.NoFocus
            and widget.isVisibleTo(self._rows_holder)
            and widget.isEnabled()
        ]

    def _step(self, delta) -> None:
        stops = self._ring()
        index = self._current_index(stops)
        if index < 0:
            index = -1 if delta == _FORWARD else 0
        for _ in range(len(stops)):
            index = (index + delta) % len(stops)
            if self._focus_stop(stops[index]):
                return

    def _current_index(self, stops) -> int:
        focus = QApplication.focusWidget()
        if focus is None:
            return -1
        for index, (kind, target) in enumerate(stops):
            if kind == _WIDGET and (target is focus or target.isAncestorOf(focus)):
                return index
            if kind == _GROUP and target.isAncestorOf(focus):
                return index
        return -1

    def _focus_stop(self, stop) -> bool:
        kind, target = stop
        if kind == _GROUP:
            focusables = self._focusables()
            if not focusables:
                return False
            focusables[0].setFocus(Qt.FocusReason.TabFocusReason)
            return True
        if not (target.isEnabled() and target.isVisible()):
            return False
        target.setFocus(Qt.FocusReason.TabFocusReason)
        return True

    def _step_within(self, focus, delta) -> bool:
        # The tree owns its own Up and Down; only the move rows use the ring's.
        if focus is not None and (
            focus is self._tree or self._tree.isAncestorOf(focus)
        ):
            return False
        focusables = self._focusables()
        if focus in focusables and len(focusables) > 1:
            index = (focusables.index(focus) + delta) % len(focusables)
            focusables[index].setFocus(Qt.FocusReason.TabFocusReason)
            return True
        return False
