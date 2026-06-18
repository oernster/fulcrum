"""Fulcrum entry point: composition root and Qt event loop."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from random import Random

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.infrastructure.json_org_importer import JsonOrgImporter
from fulcrum.infrastructure.json_save_repository import JsonSaveGameRepository
from fulcrum.infrastructure.plan_exporter import FilePlanExporter
from fulcrum.infrastructure.system_clock import SystemClock
from fulcrum.shared.resources import find_app_icon
from fulcrum.ui import ui_scale
from fulcrum.ui.main_window import MainWindow
from fulcrum.ui.theme import get_dark_qss
from fulcrum.version import APP_NAME

_UI_SCALE_REFERENCE_HEIGHT = 1260.0
_MAX_UI_SCALE = 1.5
_WIDTH_FRACTION = 0.5
_HEIGHT_FRACTION = 0.85
_MIN_WIDTH = 720
_MIN_HEIGHT = 640


def _save_directory() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home()
    return root / APP_NAME / "saves"


def _size_window(window: MainWindow, avail) -> None:
    width = min(max(int(avail.width() * _WIDTH_FRACTION), _MIN_WIDTH), avail.width())
    height = min(
        max(int(avail.height() * _HEIGHT_FRACTION), _MIN_HEIGHT), avail.height()
    )
    x = avail.x() + (avail.width() - width) // 2
    y = avail.y() + (avail.height() - height) // 2
    window.setGeometry(x, y, width, height)


def main() -> int:
    app = QApplication(sys.argv)

    avail = app.primaryScreen().availableGeometry()
    ui_scale.init(min(avail.height() / _UI_SCALE_REFERENCE_HEIGHT, _MAX_UI_SCALE))
    app.setStyleSheet(get_dark_qss())

    icon_path = find_app_icon()
    icon = QIcon(str(icon_path)) if icon_path is not None else None
    if icon is not None:
        app.setWindowIcon(icon)

    window = MainWindow(
        simulator=DeterministicSimulator(),
        save_repository=JsonSaveGameRepository(_save_directory()),
        importer=JsonOrgImporter(),
        plan_exporter=FilePlanExporter(),
        clock=SystemClock(),
        rng=Random(),
    )
    if icon is not None:
        window.setWindowIcon(icon)
    _size_window(window, avail)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
