"""Session-creating actions: model, edit, wizard and random generation.

Everything that replaces the current session with a new org lives here, split
from the main window so each module stays within the structural line limit.
"Model my organisation" starts fresh (confirming when that would discard user
work); "Edit my org" reopens the current org in the same editor, whatever its
origin, and rebuilds it with that origin preserved.
"""

from __future__ import annotations

from random import Random

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QMessageBox

from fulcrum.application.game_session import GameSession
from fulcrum.application.intake import build_org_state, org_to_blueprint
from fulcrum.application.interfaces import Simulator
from fulcrum.application.level_generator import generate_level
from fulcrum.application.dto import OrgBlueprint
from fulcrum.domain.errors import FulcrumError
from fulcrum.domain.models import Origin, OrgState
from fulcrum.domain.org_size import OrgSizeBand
from fulcrum.ui.generation_thread import GenerationThread
from fulcrum.ui.widgets.busy_dialog import BusyDialog
from fulcrum.ui.widgets.org_editor import OrgEditorDialog
from fulcrum.ui.widgets.org_size_picker import OrgSizePicker
from fulcrum.ui.widgets.org_wizard import OrgWizard

# Show the busy dialog only if generation outlasts this, so small bands that
# build in a few milliseconds never flash it.
_BUSY_DELAY_MS = 200

_DISCARD_QUESTION = (
    "Start a new organisation from scratch? The current model and its played "
    "moves will be discarded. Use Edit my org to change the current model "
    "instead."
)


class OrgIntakeController:
    """Owns the dialogs and threads that produce a new session."""

    def __init__(
        self,
        window,
        simulator: Simulator,
        rng: Random,
        session_of,
        set_session,
    ) -> None:
        self._window = window
        self._simulator = simulator
        self._rng = rng
        self._session_of = session_of
        self._set_session = set_session
        self._generation: GenerationThread | None = None

    def generate(self, band: OrgSizeBand) -> None:
        org = generate_level(self._rng, band)
        self._set_session(GameSession(org, self._simulator))

    def new_random_org(self) -> None:
        band = OrgSizePicker.choose(self._window)
        if band is not None:
            self._generate_async(band)

    def model_org(self) -> None:
        if self._has_user_model() and not self._confirm_discard():
            return
        editor = OrgEditorDialog(self._window, rng=self._rng)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        self._load_blueprint(editor.to_blueprint(), Origin.WIZARD)

    def edit_org(self) -> None:
        session = self._session_of()
        if session is None:
            return
        editor = OrgEditorDialog(
            self._window,
            blueprint=org_to_blueprint(session.org),
            rng=self._rng,
        )
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        self._load_blueprint(editor.to_blueprint(), session.org.origin)

    def quick_org(self) -> None:
        wizard = OrgWizard(self._window, rng=self._rng)
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        self._load_blueprint(wizard.to_blueprint(), Origin.WIZARD)

    def shutdown(self) -> None:
        """Wait for a running generation so the app closes without a crash."""
        if self._generation is not None:
            self._generation.wait()

    # -------------------------------------------------------------- internal

    def _has_user_model(self) -> bool:
        """Whether discarding the current session would lose user work."""
        session = self._session_of()
        if session is None:
            return False
        return bool(session.history) or session.org.origin != Origin.GENERATED

    def _confirm_discard(self) -> bool:
        answer = QMessageBox.question(
            self._window,
            "Model my organisation",
            _DISCARD_QUESTION,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _load_blueprint(self, blueprint: OrgBlueprint, origin: Origin) -> None:
        try:
            org = build_org_state(blueprint, origin)
        except FulcrumError as error:
            QMessageBox.warning(
                self._window, "Could not build organisation", str(error)
            )
            return
        self._set_session(GameSession(org, self._simulator))

    def _generate_async(self, band: OrgSizeBand) -> None:
        self._generation = GenerationThread(self._rng, band)
        self._generation.generated.connect(self._on_generated)
        self._generation.finished.connect(self._generation.deleteLater)
        self._busy = BusyDialog("Generating organisation...", self._window)
        self._busy_timer = QTimer(self._window)
        self._busy_timer.setSingleShot(True)
        self._busy_timer.timeout.connect(self._busy.show)
        self._busy_timer.start(_BUSY_DELAY_MS)
        self._generation.start()

    def _on_generated(self, org: OrgState) -> None:
        self._busy_timer.stop()
        self._busy.close()
        self._set_session(GameSession(org, self._simulator))
