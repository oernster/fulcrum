"""The Fulcrum main window: menus, the prominent wizard button and the board."""

from __future__ import annotations

from random import Random

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fulcrum.application.dto import OrgBlueprint, Plan
from fulcrum.application.game_session import GameSession
from fulcrum.application.intake import build_org_state
from fulcrum.application.interfaces import (
    Clock,
    OrgImporter,
    PlanExporter,
    SaveGameRepository,
    Simulator,
)
from fulcrum.application.level_generator import generate_level
from fulcrum.application.plan import build_plan_report
from fulcrum.application.plan_edit import first_invalid_index
from fulcrum.application.planner import ImprovementPlanner
from fulcrum.domain.errors import FulcrumError
from fulcrum.domain.hierarchy import child_domains, focused_suborg
from fulcrum.domain.models import Origin
from fulcrum.domain.org_size import DEFAULT_BAND, OrgSizeBand
from fulcrum.shared.resources import find_model_licence, find_ui_licence
from fulcrum.ui.widgets.about_dialog import AboutDialog, LicenceDialog
from fulcrum.ui.widgets.board_view import BoardView
from fulcrum.ui.widgets.book_background_dialog import BookBackgroundDialog
from fulcrum.ui.widgets.glossary_dialog import GlossaryDialog
from fulcrum.ui.widgets.guide_dialog import GuideDialog
from fulcrum.ui.widgets.org_editor import OrgEditorDialog
from fulcrum.ui.widgets.org_overview_dialog import OrgOverviewDialog
from fulcrum.ui.widgets.org_size_picker import OrgSizePicker
from fulcrum.ui.widgets.org_wizard import OrgWizard
from fulcrum.ui.widgets.plan_editor import PlanEditorDialog
from fulcrum.version import APP_NAME, APP_TAGLINE

_DEFAULT_SLOT = "slot1"
_IMPORT_FILTER = "Org JSON (*.json);;All files (*)"
_HTML_FILTER = "HTML report (*.html);;All files (*)"
_PLAN_FILTER = "Plan JSON (*.json);;All files (*)"
_DEFAULT_HTML_EXPORT = "fulcrum-plan.html"
_DEFAULT_JSON_EXPORT = "fulcrum-plan.json"
_GLOSSARY_GLYPH = "\N{SCROLL}"
_GLOSSARY_TOOLTIP = "Decision glossary"
_OVERVIEW_GLYPH = "\N{WORLD MAP}\N{VARIATION SELECTOR-16}"
_OVERVIEW_TOOLTIP = "Organisation overview"


class MainWindow(QMainWindow):
    """Wires the application services to the board and the menus."""

    def __init__(
        self,
        simulator: Simulator,
        save_repository: SaveGameRepository,
        importer: OrgImporter,
        plan_exporter: PlanExporter,
        clock: Clock,
        rng: Random,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._simulator = simulator
        self._save_repository = save_repository
        self._importer = importer
        self._plan_exporter = plan_exporter
        self._clock = clock
        self._rng = rng
        self._session: GameSession | None = None

        self.setWindowTitle(f"{APP_NAME} - {APP_TAGLINE}")
        self._board = BoardView()
        self._build_menu()
        self._build_central()
        self._generate(DEFAULT_BAND)

    def _build_central(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        top = QHBoxLayout()
        model_button = QPushButton("Model my organisation")
        model_button.setObjectName("Primary")
        model_button.clicked.connect(self._model_org)
        new_button = QPushButton("New random organisation")
        new_button.clicked.connect(self._new_random_org)
        guide_button = QPushButton("Show the guide")
        guide_button.clicked.connect(self._show_guide)
        top.addWidget(model_button)
        top.addWidget(new_button)
        top.addWidget(guide_button)
        top.addStretch()
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

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction("New random organisation...", self._new_random_org)
        file_menu.addAction("Model my organisation...", self._model_org)
        file_menu.addAction("Quick org (wizard)...", self._quick_org)
        file_menu.addAction("Import organisational state...", self._import_org)
        file_menu.addSeparator()
        file_menu.addAction("Save game...", self._save_game)
        file_menu.addAction("Load game...", self._load_game)
        file_menu.addSeparator()
        file_menu.addAction("Export plan as HTML...", self._export_plan_html)
        file_menu.addAction("Export plan as JSON...", self._export_plan_json)
        file_menu.addAction("Edit a plan...", self._edit_plan)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction("Organisation overview...", self._org_overview)

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction("Decision glossary...", self._glossary)
        help_menu.addAction("Book background...", self._book_background)
        help_menu.addSeparator()
        help_menu.addAction("About", self._about)
        help_menu.addAction("Model licence (GPL-3.0)", self._model_licence)
        help_menu.addAction("UI licence (LGPL-3.0)", self._ui_licence)

    def _set_session(self, session: GameSession) -> None:
        self._session = session
        self._board.set_session(session)

    def _generate(self, band: OrgSizeBand) -> None:
        org = generate_level(self._rng, band)
        self._set_session(GameSession(org, self._simulator))

    def _new_random_org(self) -> None:
        band = OrgSizePicker.choose(self)
        if band is not None:
            self._generate(band)

    def _show_guide(self) -> None:
        if self._session is None:
            return
        org = self._session.org
        focused = self._session.focused_on
        if focused is None or child_domains(org, focused):
            self._inform(
                "Guide",
                "Drill into a section on the map first. The guide plans the "
                "section you are in, where the strong moves are.",
            )
            return
        section = focused_suborg(org, focused)
        fixed = ImprovementPlanner(self._simulator).plan(section)
        grown = ImprovementPlanner(self._simulator, allow_growth=True).plan(section)
        GuideDialog(fixed, grown, self).exec()

    def _model_org(self) -> None:
        editor = OrgEditorDialog(self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        self._load_blueprint(editor.to_blueprint(), Origin.WIZARD)

    def _quick_org(self) -> None:
        wizard = OrgWizard(self)
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        self._load_blueprint(wizard.to_blueprint(), Origin.WIZARD)

    def _import_org(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import organisational state", "", _IMPORT_FILTER
        )
        if not path:
            return
        try:
            blueprint = self._importer.import_org(path)
        except FulcrumError as error:
            self._warn("Import failed", str(error))
            return
        self._load_blueprint(blueprint, Origin.IMPORTED)

    def _load_blueprint(self, blueprint: OrgBlueprint, origin: Origin) -> None:
        try:
            org = build_org_state(blueprint, origin)
        except FulcrumError as error:
            self._warn("Could not build organisation", str(error))
            return
        self._set_session(GameSession(org, self._simulator))

    def _save_game(self) -> None:
        if self._session is None:
            return
        slot, ok = QInputDialog.getText(
            self, "Save game", "Slot name:", text=_DEFAULT_SLOT
        )
        if ok and slot:
            self._session.save(self._save_repository, slot, self._clock)

    def _load_game(self) -> None:
        slots = self._save_repository.slots()
        if not slots:
            self._warn("Load game", "There are no saved games yet.")
            return
        slot, ok = QInputDialog.getItem(
            self, "Load game", "Slot:", list(slots), 0, False
        )
        if ok and slot:
            saved = self._save_repository.load(slot)
            self._set_session(GameSession.from_saved_game(saved, self._simulator))

    def _export_plan_html(self) -> None:
        if self._session is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export plan as HTML", _DEFAULT_HTML_EXPORT, _HTML_FILTER
        )
        if not path:
            return
        created = self._clock.timestamp()
        report = build_plan_report(
            self._session.initial_org, self._session.history, self._simulator
        )
        self._plan_exporter.export_html(
            path, report, self._session.initial_org, self._session.org, created
        )
        self._inform("Plan exported", "Wrote the HTML report.")

    def _export_plan_json(self) -> None:
        if self._session is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export plan as JSON", _DEFAULT_JSON_EXPORT, _PLAN_FILTER
        )
        if not path:
            return
        created = self._clock.timestamp()
        plan = Plan(self._session.initial_org, self._session.history, created)
        self._plan_exporter.export_json(path, plan)
        self._inform("Plan exported", "Wrote the JSON plan you can re-import to edit.")

    def _edit_plan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Edit a plan", "", _PLAN_FILTER)
        if not path:
            return
        try:
            plan = self._plan_exporter.read(path)
        except (OSError, ValueError, KeyError, FulcrumError) as error:
            self._warn("Could not open plan", str(error))
            return
        dialog = PlanEditorDialog(plan, self._simulator, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        moves = dialog.edited_moves()
        cut = first_invalid_index(plan.initial_org, moves)
        if cut is not None:
            moves = moves[:cut]
            self._inform("Plan trimmed", "Moves that no longer applied were dropped.")
        session = GameSession(plan.initial_org, self._simulator)
        for move in moves:
            session.play(move)
        self._set_session(session)

    def _glossary(self) -> None:
        GlossaryDialog(self).exec()

    def _org_overview(self) -> None:
        if self._session is None:
            return
        OrgOverviewDialog(self._session.org, self).exec()

    def _book_background(self) -> None:
        BookBackgroundDialog(self).exec()

    def _about(self) -> None:
        AboutDialog(self).exec()

    def _model_licence(self) -> None:
        LicenceDialog("Model licence - GPL-3.0", find_model_licence(), self).exec()

    def _ui_licence(self) -> None:
        LicenceDialog("UI licence - LGPL-3.0", find_ui_licence(), self).exec()

    def _warn(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def _inform(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)
