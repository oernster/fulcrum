"""The Fulcrum main window: menus, the header tray and the board."""

from __future__ import annotations

from random import Random

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
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
    SettingsStore,
    Simulator,
)
from fulcrum.domain.org_size import DEFAULT_BAND
from fulcrum.shared.resources import (
    find_model_licence,
    find_ui_licence,
)
from fulcrum.ui import header_buttons
from fulcrum.ui.close_guard import install_close_guard
from fulcrum.ui.guide_launcher import GuideLauncher
from fulcrum.ui.icons import button_icon
from fulcrum.ui.map_palette import set_map_theme
from fulcrum.ui.org_intake import OrgIntakeController
from fulcrum.ui.plan_files import PlanFileActions
from fulcrum.ui.theme import get_qss
from fulcrum.ui.theme_palettes import DEFAULT_THEME, THEME_DARK, THEME_LIGHT
from fulcrum.ui.widgets import disabled_cue
from fulcrum.ui.widgets.about_dialog import AboutDialog, LicenceDialog
from fulcrum.ui.widgets.board_view import BoardView
from fulcrum.ui.widgets.book_background_dialog import BookBackgroundDialog
from fulcrum.ui.widgets.glossary_dialog import GlossaryDialog
from fulcrum.ui.widgets.keyboard_nav import KeyboardNavigator
from fulcrum.ui.widgets.move_record_dialog import MoveRecordDialog
from fulcrum.ui.widgets.provenance_dialog import ProvenanceDialog
from fulcrum.version import APP_NAME, APP_TAGLINE

_RELEASES_URL = "https://github.com/oernster/fulcrum/releases"
_GLOSSARY_GLYPH = "\N{INFORMATION SOURCE}\N{VARIATION SELECTOR-16}"
_GLOSSARY_TOOLTIP = "Decision glossary"
_RECORD_TOOLTIP = "Move record: every move to date, with the position before and after"
_PRESENTATION_GLYPH = "\N{CHART WITH UPWARDS TREND}"
_PRESENTATION_TOOLTIP = "Create presentation"
_MODEL_ORG_TOOLTIP = "Model my organisation"
_EDIT_ORG_TOOLTIP = "Edit my org: reopen and edit the current organisation"
_GUIDE_TOOLTIP = "Show the guide"
_PROVENANCE_TOOLTIP = (
    "What grounds the numbers: every coefficient, its source and its fragility"
)


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
        settings: SettingsStore | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._simulator = simulator
        self._org_store = org_store
        self._settings = settings
        self._theme = settings.load_theme() if settings is not None else DEFAULT_THEME
        set_map_theme(self._theme)
        # The generated header icons carry a variant per theme; the toggle
        # re-dresses each of these (button, icon name) pairs on switch.
        self._themed_icon_buttons: list[tuple[QPushButton, str]] = []
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
        self._guide_launcher = GuideLauncher(
            self,
            simulator,
            lambda: self._session,
            self._board.refresh,
            self._inform,
            lambda: self._theme,
        )
        restored = org_store.load() if org_store is not None else None
        # A failed restore is not the same as having nothing to restore, and
        # the user is the only one who can tell which happened. Held until
        # the window is shown, since a message box during construction has no
        # parent to sit over.
        self._restore_warning = self._restore_warning_text(org_store)
        if restored is not None:
            # Replay rebuilds the undo stack, so the whole record (this
            # run's predecessor included) can be taken back move by move.
            self._set_session(restore_session(restored, self._simulator))
        else:
            self._intake.generate(DEFAULT_BAND)
        # A taskbar close must quit even while a dialog is modal; Qt drops
        # that close before any filter can see it, so a native guard
        # dismisses the modals and runs the normal close flow instead.
        self._close_guard = install_close_guard(self)

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
        # The app icon sits at the centre of the tray and opens the move
        # record; the complete overview lives on the board itself now.
        record_button = header_buttons.app_icon_button(
            _RECORD_TOOLTIP, self._move_record
        )
        top.addWidget(record_button)
        # Its golden kin sits beside it and answers why the numbers are
        # what they are: the model's provenance, coefficient by coefficient.
        provenance_button = header_buttons.provenance_icon_button(
            _PROVENANCE_TOOLTIP, self._provenance
        )
        top.addWidget(provenance_button)
        top.addStretch()
        presentation_link = QPushButton(_PRESENTATION_GLYPH)
        presentation_link.setObjectName("IconLink")
        presentation_link.setToolTip(_PRESENTATION_TOOLTIP)
        presentation_link.setCursor(Qt.CursorShape.PointingHandCursor)
        presentation_link.clicked.connect(self._plan_files.export_html)
        presentation_link.setEnabled(False)
        self._board.historyChanged.connect(presentation_link.setEnabled)
        self._theme_toggle = header_buttons.theme_toggle_button(self._toggle_theme)
        header_buttons.dress_theme_toggle(self._theme_toggle, self._theme)
        top.addWidget(self._theme_toggle)
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
                record_button,
                provenance_button,
                self._theme_toggle,
                presentation_link,
                glossary_link,
            )
        )
        disabled_cue.install(
            self,
            (presentation_link, self._undo_button),
            (self._presentation_action, self._undo_action),
        )

    def _toggle_theme(self) -> None:
        self._theme = THEME_LIGHT if self._theme == THEME_DARK else THEME_DARK
        QApplication.instance().setStyleSheet(get_qss(self._theme))
        set_map_theme(self._theme)
        if self._settings is not None:
            self._settings.save_theme(self._theme)
        header_buttons.dress_theme_toggle(self._theme_toggle, self._theme)
        for button, name in self._themed_icon_buttons:
            button.setIcon(button_icon(name, self._theme))
        # The map paints its own colours; rebuild the board so the canvas,
        # nodes and edges repaint in the new palette immediately.
        self._board.apply_map_theme()
        self._board.refresh()

    def _icon_button(self, name: str, tooltip: str, handler) -> QPushButton:
        button = header_buttons.icon_button(name, tooltip, handler, self._theme)
        self._themed_icon_buttons.append((button, name))
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
        view_menu.addAction("Move record...", self._move_record)

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
        self._guide_launcher.show()

    def _glossary(self) -> None:
        GlossaryDialog(self).exec()

    def _provenance(self) -> None:
        ProvenanceDialog(self).exec()

    def _move_record(self) -> None:
        if self._session is None:
            return
        MoveRecordDialog(
            self._session.initial_org,
            self._session.history,
            self._session.prior_history_count,
            self._simulator,
            self,
            self._theme,
        ).exec()

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

    @staticmethod
    def _restore_warning_text(org_store) -> str | None:
        """Explain a failed restore, or None when there is nothing to explain."""
        if org_store is None:
            return None
        if org_store.preserved_copy is not None:
            return (
                "The saved organisation could not be read, so it has been kept "
                f"at {org_store.preserved_copy} and a new one has been started. "
                "Nothing has been deleted."
            )
        if org_store.is_sealed:
            return (
                "The saved organisation could not be read and could not be "
                "moved aside, so it has been left untouched. This session will "
                "not be saved over it."
            )
        return None

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._started:
            self._started = True
            self._focus_start.setFocus(Qt.FocusReason.OtherFocusReason)
            if self._restore_warning is not None:
                self._inform("Saved organisation", self._restore_warning)
                self._restore_warning = None

    def closeEvent(self, event) -> None:
        self._autosave()
        self._board.stop_analysis()
        self._intake.shutdown()
        super().closeEvent(event)
