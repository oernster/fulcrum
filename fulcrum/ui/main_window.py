"""The Fulcrum main window: menus, the prominent wizard button and the board."""

from __future__ import annotations

from random import Random

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.game_session import GameSession, restore_session
from fulcrum.application.interfaces import (
    Clock,
    ExampleSource,
    OrgStore,
    PlanExporter,
    Simulator,
)
from fulcrum.application.org_guide import build_org_guide
from fulcrum.domain.org_size import DEFAULT_BAND
from fulcrum.shared.resources import (
    find_about_png,
    find_model_licence,
    find_ui_licence,
)
from fulcrum.ui import ui_scale
from fulcrum.ui.guide_thread import OrgGuideThread
from fulcrum.ui.icons import button_icon
from fulcrum.ui.org_intake import OrgIntakeController
from fulcrum.ui.plan_files import PlanFileActions
from fulcrum.ui.widgets import disabled_cue
from fulcrum.ui.widgets.about_dialog import AboutDialog, LicenceDialog
from fulcrum.ui.widgets.board_view import BoardView
from fulcrum.ui.widgets.book_background_dialog import BookBackgroundDialog
from fulcrum.ui.widgets.busy_dialog import BusyDialog
from fulcrum.ui.widgets.glossary_dialog import GlossaryDialog
from fulcrum.ui.widgets.keyboard_nav import KeyboardNavigator
from fulcrum.ui.widgets.org_guide_dialog import OrgGuideDialog
from fulcrum.ui.widgets.org_overview_dialog import OrgOverviewDialog
from fulcrum.version import APP_NAME, APP_TAGLINE

_RELEASES_URL = "https://github.com/oernster/fulcrum/releases"
_GLOSSARY_GLYPH = "\N{SCROLL}"
_GLOSSARY_TOOLTIP = "Decision glossary"
_OVERVIEW_GLYPH = "\N{WORLD MAP}\N{VARIATION SELECTOR-16}"
_OVERVIEW_TOOLTIP = "Organisation overview"
_PRESENTATION_GLYPH = "\N{CHART WITH UPWARDS TREND}"
_PRESENTATION_TOOLTIP = "Create presentation"
_MODEL_ORG_TOOLTIP = "Model my organisation"
_EDIT_ORG_TOOLTIP = "Edit my org: reopen and edit the current organisation"
_GUIDE_TOOLTIP = "Show the guide"
_BUTTON_ICON_PX = 24
_APP_ICON_PX = 28


class MainWindow(QMainWindow):
    """Wires the application services to the board and the menus."""

    def __init__(
        self,
        simulator: Simulator,
        plan_exporter: PlanExporter,
        clock: Clock,
        rng: Random,
        examples: ExampleSource,
        org_store: OrgStore | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._simulator = simulator
        self._org_store = org_store
        self._session: GameSession | None = None
        self._started = False
        self._intake = OrgIntakeController(
            self,
            simulator,
            rng,
            lambda: self._session,
            self._set_session,
            examples,
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
        # Every play and take-back lands in the autosave immediately, so
        # the move record survives however the app ends.
        self._board.historyChanged.connect(lambda _can: self._autosave())
        restored = org_store.load() if org_store is not None else None
        if restored is not None:
            # Replay rebuilds the undo stack, so the whole record (this
            # run's predecessor included) can be taken back move by move.
            self._set_session(restore_session(restored, self._simulator))
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
        model_button = self._icon_button(
            "model_org", _MODEL_ORG_TOOLTIP, self._intake.model_org
        )
        edit_button = self._icon_button(
            "edit_org", _EDIT_ORG_TOOLTIP, self._intake.edit_org
        )
        guide_button = self._icon_button("guide", _GUIDE_TOOLTIP, self._show_guide)
        top.addWidget(model_button)
        top.addWidget(edit_button)
        top.addWidget(guide_button)
        top.addStretch()
        # The app icon sits at the centre of the tray and opens the
        # organisation overview.
        overview_button = QPushButton()
        overview_button.setObjectName("IconLink")
        icon_path = find_about_png()
        if icon_path is not None:
            overview_button.setIcon(QIcon(str(icon_path)))
        overview_button.setIconSize(
            QSize(ui_scale.px(_APP_ICON_PX), ui_scale.px(_APP_ICON_PX))
        )
        overview_button.setToolTip(_OVERVIEW_TOOLTIP)
        overview_button.setAccessibleName(_OVERVIEW_TOOLTIP)
        overview_button.setCursor(Qt.CursorShape.PointingHandCursor)
        overview_button.clicked.connect(self._org_overview)
        top.addWidget(overview_button)
        top.addStretch()
        presentation_link = QPushButton(_PRESENTATION_GLYPH)
        presentation_link.setObjectName("IconLink")
        presentation_link.setToolTip(_PRESENTATION_TOOLTIP)
        presentation_link.setCursor(Qt.CursorShape.PointingHandCursor)
        presentation_link.clicked.connect(self._plan_files.export_html)
        presentation_link.setEnabled(False)
        self._board.historyChanged.connect(presentation_link.setEnabled)
        top.addWidget(presentation_link)
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
                guide_button,
                overview_button,
                presentation_link,
                glossary_link,
            )
        )
        disabled_cue.install(
            self,
            (presentation_link, self._undo_button),
            (self._presentation_action, self._undo_action),
        )

    def _icon_button(self, name: str, tooltip: str, handler) -> QPushButton:
        """An icon-only header button whose old text lives on as the tooltip."""
        button = QPushButton()
        button.setIcon(button_icon(name))
        button.setIconSize(
            QSize(ui_scale.px(_BUTTON_ICON_PX), ui_scale.px(_BUTTON_ICON_PX))
        )
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(handler)
        return button

    def _install_keyboard_nav(self, buttons) -> None:
        undo_button, map_view, level_button, moves_group, signals_group = (
            self._board.nav_targets()
        )
        self._undo_button = undo_button
        self._nav = KeyboardNavigator(
            self,
            self.menuBar(),
            self.menuBar().actions(),
            (*buttons, undo_button, map_view, level_button),
            (moves_group, signals_group),
            map_view,
            neutral_start=self._focus_start,
        )

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
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

        org_menu = self.menuBar().addMenu("Organisation")
        org_menu.addAction("New random organisation...", self._intake.new_random_org)
        org_menu.addAction("Model my organisation...", self._intake.model_org)
        org_menu.addAction("Edit my org...", self._intake.edit_org)
        org_menu.addAction("Quick org (wizard)...", self._intake.quick_org)
        example_menu = org_menu.addMenu("Open example organisation")
        example_menu.setToolTipsVisible(True)
        for summary in self._intake.example_entries():
            action = example_menu.addAction(
                summary.label,
                lambda checked=False, s=summary: self._intake.open_example(s),
            )
            if summary.note:
                action.setToolTip(summary.note)
                action.setStatusTip(summary.note)
        example_menu.menuAction().setEnabled(not example_menu.isEmpty())

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
            self._org_store.save(self._session.snapshot())

    def _show_guide(self) -> None:
        """Plan every level off-thread, then open the hierarchy guide."""
        if self._session is None:
            return
        self._guide_busy = BusyDialog("Planning every level...", self)
        self._guide_busy.show()
        self._guide_thread = OrgGuideThread(self._session.org, self._simulator)
        self._guide_thread.progress.connect(self._guide_busy.set_progress)
        self._guide_thread.built.connect(self._on_guides_built)
        self._guide_thread.finished.connect(self._guide_thread.deleteLater)
        self._guide_thread.start()

    def _on_guides_built(self, guides) -> None:
        self._guide_busy.close()
        fixed, grown = guides
        OrgGuideDialog(
            fixed, grown, self._simulator, self._play_from_guide, self
        ).exec()

    def _play_from_guide(self, move, frame_id):
        """Play a guide move live; return refreshed guides, or None if blocked."""
        if self._session is None:
            return None
        if not self._session.try_play_in_frame(move, frame_id):
            self._inform(
                "Cannot play this move yet",
                "This move builds on earlier moves in the path; play those first.",
            )
            return None
        self._board.refresh()
        org = self._session.org
        fixed = build_org_guide(org, self._simulator)
        grown = build_org_guide(org, self._simulator, allow_growth=True)
        return fixed, grown

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
