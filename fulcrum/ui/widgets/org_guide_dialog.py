"""The hierarchy guide: a plan for every level of the organisation.

Two panes, like the org editor: the left pane is the org tree with each
frame's climb ("24.5 → 78.7") on its row, so the summit-versus-leaves
asymmetry is visible at a glance; the right pane is the selected frame's
move-by-move line with preview and play, as the old single-frame guide had.
Leaf lines carry the value and compose into the headline; an aggregate row
is the view from that altitude, shown but never composed.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
from fulcrum.ui.widgets.dialog_focus_ring import (
    GROUP_STOP,
    WIDGET_STOP,
    DialogFocusRing,
)
from fulcrum.ui.widgets.move_preview_dialog import MovePreviewDialog
from fulcrum.ui.widgets.neutral_dialog import NeutralDialog

_MIN_WIDTH = 980
_MIN_HEIGHT = 560
_TREE_SHARE = 2
_STEPS_SHARE = 3
_TREE_PANE_W = 340
_STEPS_PANE_W = 640
# The dialog opens at most of the app window (or screen), like the org
# editor: a hierarchy needs the room, and both panes then fit without
# horizontal scrolling.
_PARENT_FILL = 0.85
_SCREEN_FILL = 0.80
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
        self.resize(self._initial_size(parent))
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
        # The climb column takes exactly what its short scores need and the
        # level column stretches into the rest, eliding long unit names, so
        # the climb is always fully visible at any pane width.
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        # Rows fit the viewport width; a sideways scrollbar over move rows
        # reads as covered-up UI, so it is off and long labels elide instead.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._rows_holder = QWidget()
        self._rows = QVBoxLayout(self._rows_holder)
        scroll.setWidget(self._rows_holder)
        steps_layout.addWidget(scroll, 1)

        panes = QSplitter(Qt.Orientation.Horizontal)
        panes.addWidget(self._tree)
        panes.addWidget(steps_box)
        panes.setStretchFactor(0, _TREE_SHARE)
        panes.setStretchFactor(1, _STEPS_SHARE)
        panes.setSizes([ui_scale.px(_TREE_PANE_W), ui_scale.px(_STEPS_PANE_W)])
        layout.addWidget(panes, 1)

        row = QHBoxLayout()
        self._close_button = QPushButton("Close")
        self._close_button.clicked.connect(self.accept)
        row.addStretch()
        row.addWidget(self._close_button)
        layout.addLayout(row)

        self._render_current()
        self._focus_ring = DialogFocusRing(self, self._ring, self._tree_owns_updown)

    @staticmethod
    def _initial_size(parent) -> QSize:
        """Most of the app window's size, or the screen's when parentless."""
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
        hint.setWordWrap(True)
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
        text = _step_text(index, step)
        move = QPushButton(text)
        move.setObjectName("MoveButton")
        # A long move label compresses rather than forcing the pane to
        # scroll sideways; the tooltip carries the full text.
        move.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        move.setToolTip(text)
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

    # Focus ring: grow toggle -> tree -> moves group -> Close -> wrap. The
    # tree keeps its own Up and Down; the move rows use the ring's.
    def _ring(self) -> list:
        return [
            (WIDGET_STOP, self._toggle),
            (WIDGET_STOP, self._tree),
            (GROUP_STOP, self._rows_holder),
            (WIDGET_STOP, self._close_button),
        ]

    def _tree_owns_updown(self, focus) -> bool:
        return focus is self._tree or self._tree.isAncestorOf(focus)

    def done(self, result: int) -> None:
        self._focus_ring.detach()
        super().done(result)
