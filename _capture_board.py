"""Throwaway: re-capture the site board screenshot taller so the moves show.

Usage (from repo root, venv active):
    python _capture_board.py [WIDTH] [HEIGHT] [SCALE] [OUT]

Renders on the real Windows platform with WA_DontShowOnScreen (no visible
window, no offscreen font tofu). HiDPI scaling is pinned off so the grab is 1:1
with the logical size. Delete this script after use.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from random import Random

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
os.environ.setdefault("QT_SCALE_FACTOR", "1")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from fulcrum.application.simulator import DeterministicSimulator  # noqa: E402
from fulcrum.domain.models import Origin  # noqa: E402
from fulcrum.infrastructure.json_org_importer import JsonOrgImporter  # noqa: E402
from fulcrum.infrastructure.json_save_repository import (  # noqa: E402
    JsonSaveGameRepository,
)
from fulcrum.infrastructure.plan_exporter import FilePlanExporter  # noqa: E402
from fulcrum.infrastructure.system_clock import SystemClock  # noqa: E402
from fulcrum.ui import ui_scale  # noqa: E402
from fulcrum.ui.main_window import MainWindow  # noqa: E402
from fulcrum.ui.theme import get_dark_qss  # noqa: E402

WIDTH = int(sys.argv[1]) if len(sys.argv) > 1 else 1283
HEIGHT = int(sys.argv[2]) if len(sys.argv) > 2 else 1300
SCALE = float(sys.argv[3]) if len(sys.argv) > 3 else 1.15
OUT = (
    sys.argv[4]
    if len(sys.argv) > 4
    else os.path.join("docs", "assets", "screenshots", "_play-board-new.png")
)
ORG = os.path.join("examples", "org-3-enterprise.json")


def main() -> int:
    app = QApplication(sys.argv[:1])
    ui_scale.init(SCALE)
    app.setStyleSheet(get_dark_qss())

    saves = Path(tempfile.gettempdir()) / "fulcrum-shot-saves"
    window = MainWindow(
        simulator=DeterministicSimulator(),
        save_repository=JsonSaveGameRepository(saves),
        importer=JsonOrgImporter(),
        plan_exporter=FilePlanExporter(),
        clock=SystemClock(),
        rng=Random(0),
    )
    blueprint = JsonOrgImporter().import_org(ORG)
    window._load_blueprint(blueprint, Origin.IMPORTED)

    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(WIDTH, HEIGHT)
    window.show()
    app.processEvents()
    window._board._map._fit()
    app.processEvents()

    pixmap = window.grab()
    pixmap.save(OUT)
    print(f"saved {OUT} {pixmap.width()} x {pixmap.height()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
