"""The Fulcrum main window: menus, the prominent wizard button and the board."""

from __future__ import annotations

from random import Random

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.game_session import GameSession
from fulcrum.application.interfaces import Clock, OrgStore, PlanExporter, Simulator
from fulcrum.application.planner import ImprovementPlanner
from fulcrum.domain.hierarchy import (
    AGGREGATE_MOVE_KINDS,
    child_domains,
    focused_suborg,
)
from fulcrum.domain.org_size import DEFAULT_BAND
from fulcrum.shared.resources import find_model_licence, find_ui_licence
from fulcrum.ui.org_intake import OrgIntakeController
from fulcrum.ui.plan_files import PlanFileActions
from fulcrum.ui.widgets.about_dialog import AboutDialog, LicenceDialog
from fulcrum.ui.widgets.board_view import BoardView
from fulcrum.ui.widgets.book_background_dialog import BookBackgroundDialog
from fulcrum.ui.widgets import disabled_cue
from fulcrum.ui.widgets.glossary_dialog import GlossaryDialog
from fulcrum.ui.widgets.guide_dialog import GuideDialog
from fulcrum.ui.widgets.keyboard_nav import KeyboardNavigator
from fulcrum.ui.widgets.org_overview_dialog import OrgOverviewDialog
from fulcrum.version import APP_NAME, APP_TAGLINE

_RELEASES_URL = "https://github.com/oernster/fulcrum/releases"
_GLOSSARY_GLYPH = "\N{SCROLL}"
_GLOSSARY_TOOLTIP = "Decision glossary"
_OVERVIEW_GLYPH = "\N{WORLD MAP}\N{VARIATION SELECTOR-16}"
_OVERVIEW_TOOLTIP = "Organisation overview"
_PRESENTATION_GLYPH = "\N{CHART WITH UPWARDS TREND}"
_PRESENTATION_TOOLTIP = "Create presentation"
_EDIT_ORG_TOOLTIP = "Reopen and edit the current organisation"


class MainWindow(QMainWindow):
    """Wires the application services to the board and the menus."""

    def __init__(
        self,
        simulator: Simulator,
        plan_exporter: PlanExporter,
        clock: Clock,
        rng: Random,
        org_store: OrgStore | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._simulator = simulator
        self._org_store = org_store
        self._session: GameSession | None = None
        self._started = False
        self._intake = OrgIntakeController(
            self, simulator, rng, lambda: self._session, self._set_session
        )
        self._plan_files = PlanFileActions(
            self,
            simulator,
            plan_exporter,
            clock,
            lambda: self._session,
            self._set_session,
        )

        self.setWindowTitle(f"{APP_NAME} - {APP_TAGLINE}")
        self._board = BoardView()
        self._build_menu()
        self._build_central()
        restored = org_store.load() if org_store is not None else None
        if restored is not None:
            self._set_session(GameSession(restored, self._simulator))
        else:
            self._intake.generate(DEFAULT_BAND)

    def _build_central(self) -> None:
        central = QWidget()
        # An invisible, focusable start item: on launch nothing is highlighted
        # and no menu drops; the first Tab or Right enters the ring. Mirrors
        # Meridian's initialFocusItem.
        self._focus_start = QWidget(central)
        self._focus_start.setFixedSize(0, 0)
        self._focus_start.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        layout = QVBoxLayout(central)
        top = QHBoxLayout()
        model_button = QPushButton("Model my organisation")
        model_button.setObjectName("Primary")
        model_button.clicked.connect(self._intake.model_org)
        edit_button = QPushButton("Edit my org")
        edit_button.setToolTip(_EDIT_ORG_TOOLTIP)
        edit_button.clicked.connect(self._intake.edit_org)
        new_button = QPushButton("New random organisation")
        new_button.clicked.connect(self._intake.new_random_org)
        guide_button = QPushButton("Show the guide")
        guide_button.clicked.connect(self._show_guide)
        top.addWidget(model_button)
        top.addWidget(edit_button)
        top.addWidget(new_button)
        top.addWidget(guide_button)
        top.addStretch()
        presentation_link = QPushButton(_PRESENTATION_GLYPH)
        presentation_link.setObjectName("IconLink")
        presentation_link.setToolTip(_PRESENTATION_TOOLTIP)
        presentation_link.setCursor(Qt.CursorShape.PointingHandCursor)
        presentation_link.clicked.connect(self._plan_files.export_html)
        presentation_link.setEnabled(False)
        self._board.historyChanged.connect(presentation_link.setEnabled)
        top.addWidget(presentation_link)
        overview_link = QPushButton(_OVERVIEW_GLYPH)
        overview_link.setObjectName("IconLink")
        overview_link.setToolTip(_OVERVIEW_TOOLTIP)
        overview_link.setCursor(Qt.CursorShape.PointingHandCursor)
        overview_link.clicked.connect(self._org_overview)
        top.addWidget(overview_link)
        glossary_link = QPushButton(_GLOSSARY_GLYPH)
        glossary_link.setObjectName("IconLink")
        glossary_link.setToolTip(_GLOSSARY_TOOLTIP)
        glossary_link.setCursor(Qt.CursorShape.PointingHandCursor)
        glossary_link.clicked.connect(self._glossary)
        top.addWidget(glossary_link)
        layout.addLayout(top)
        layout.addWidget(self._board, 1)
        self.setCentralWidget(central)
        self._install_keyboard_nav(
            (
                model_button,
                edit_button,
                new_button,
                guide_button,
                presentation_link,
                overview_link,
                glossary_link,
            )
        )
        disabled_cue.install(
            self,
            (presentation_link, self._undo_button),
            (self._presentation_action, self._undo_action),
        )

    def _install_keyboard_nav(self, buttons) -> None:
        undo_button, map_view, moves_group, signals_group = self._board.nav_targets()
        self._undo_button = undo_button
        self._nav = KeyboardNavigator(
            self,
            self.menuBar(),
            self.menuBar().actions(),
            (*buttons, undo_button, map_view),
            (moves_group, signals_group),
            map_view,
        )

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction("New random organisation...", self._intake.new_random_org)
        file_menu.addAction("Model my organisation...", self._intake.model_org)
        file_menu.addAction("Edit my org...", self._intake.edit_org)
        file_menu.addAction("Quick org (wizard)...", self._intake.quick_org)
        file_menu.addSeparator()
        self._presentation_action = file_menu.addAction(
            "Create presentation...", self._plan_files.export_html
        )
        self._presentation_action.setEnabled(False)
        self._board.historyChanged.connect(self._presentation_action.setEnabled)
        file_menu.addSeparator()
        file_menu.addAction("Import...", self._plan_files.import_plan)
        file_menu.addAction("Export...", self._plan_files.export_json)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        edit_menu = self.menuBar().addMenu("Edit")
        self._undo_action = edit_menu.addAction(
            "Take a move back", self._board.take_back
        )
        self._undo_action.setShortcut("Ctrl+Z")
        self._undo_action.setEnabled(False)
        self._board.historyChanged.connect(self._undo_action.setEnabled)

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction("Organisation overview...", self._org_overview)

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction("Decision glossary...", self._glossary)
        help_menu.addAction("Book background...", self._book_background)
        help_menu.addAction("Check for updates...", self._check_for_updates)
        help_menu.addSeparator()
        help_menu.addAction("About", self._about)
        help_menu.addAction("Model licence (GPL-3.0)", self._model_licence)
        help_menu.addAction("UI licence (LGPL-3.0)", self._ui_licence)

    def _set_session(self, session: GameSession) -> None:
        self._session = session
        self._board.set_session(session)
        self._autosave()

    def _autosave(self) -> None:
        if self._org_store is not None and self._session is not None:
            self._org_store.save(self._session.org)

    def _show_guide(self) -> None:
        if self._session is None:
            return
        if not self._session.is_active_scope_playable():
            self._inform(
                "Guide",
                "This scope is too large to plan. Drill into a section on the "
                "map first, then open the guide there.",
            )
            return
        fixed, grown = self._plan_guides()
        GuideDialog(fixed, grown, self._simulator, self._play_from_guide, self).exec()

    def _plan_guides(self):
        org = self._session.org
        focused = self._session.focused_on
        section = focused_suborg(org, focused) if focused is not None else org
        aggregate = focused is not None and bool(child_domains(org, focused))
        kinds = AGGREGATE_MOVE_KINDS if aggregate else None
        fixed = ImprovementPlanner(self._simulator).plan(section, kinds)
        grown = ImprovementPlanner(self._simulator, allow_growth=True).plan(
            section, kinds
        )
        return fixed, grown

    def _play_from_guide(self, move):
        """Play a guide move live; return the refreshed plan, or None if blocked."""
        if self._session is None:
            return None
        if not self._session.try_play(move):
            self._inform(
                "Cannot play this move yet",
                "This move builds on earlier moves in the path; play those first.",
            )
            return None
        self._board.refresh()
        return self._plan_guides()

    def _glossary(self) -> None:
        GlossaryDialog(self).exec()

    def _org_overview(self) -> None:
        if self._session is None:
            return
        OrgOverviewDialog(self._session.org, self).exec()

    def _book_background(self) -> None:
        BookBackgroundDialog(self).exec()

    def _check_for_updates(self) -> None:
        QDesktopServices.openUrl(QUrl(_RELEASES_URL))

    def _about(self) -> None:
        AboutDialog(self).exec()

    def _model_licence(self) -> None:
        LicenceDialog("Model licence - GPL-3.0", find_model_licence(), self).exec()

    def _ui_licence(self) -> None:
        LicenceDialog("UI licence - LGPL-3.0", find_ui_licence(), self).exec()

    def _inform(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._started:
            self._started = True
            self._focus_start.setFocus(Qt.FocusReason.OtherFocusReason)

    def closeEvent(self, event) -> None:
        self._autosave()
        self._board.stop_analysis()
        self._intake.shutdown()
        super().closeEvent(event)
