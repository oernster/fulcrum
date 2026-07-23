"""Fulcrum entry point: composition root and Qt event loop."""

from __future__ import annotations

import sys
from random import Random

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.infrastructure.org_autosave import FileOrgStore
from fulcrum.infrastructure.plan_exporter import FilePlanExporter
from fulcrum.infrastructure.system_clock import SystemClock
from fulcrum.shared.resources import find_app_icon
from fulcrum.ui import ui_scale
from fulcrum.ui.main_window import MainWindow
from fulcrum.ui.theme import get_dark_qss

_UI_SCALE_REFERENCE_HEIGHT = 1260.0
_MAX_UI_SCALE = 1.5
_WIDTH_FRACTION = 0.5
_HEIGHT_FRACTION = 0.85
_MIN_WIDTH = 720
_MIN_HEIGHT = 640


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

    # The app is themed entirely by stylesheet. The native windows11 style
    # paints its own chrome over stylesheet borders (truncated focus and
    # hover rings on combos and fields), so pin the style Fusion renders
    # QSS faithfully on and every platform shares.
    app.setStyle("fusion")

    avail = app.primaryScreen().availableGeometry()
    ui_scale.init(min(avail.height() / _UI_SCALE_REFERENCE_HEIGHT, _MAX_UI_SCALE))
    app.setStyleSheet(get_dark_qss())

    icon_path = find_app_icon()
    icon = QIcon(str(icon_path)) if icon_path is not None else None
    if icon is not None:
        app.setWindowIcon(icon)

    window = MainWindow(
        simulator=DeterministicSimulator(),
        plan_exporter=FilePlanExporter(),
        clock=SystemClock(),
        rng=Random(),
        org_store=FileOrgStore(),
    )
    if icon is not None:
        window.setWindowIcon(icon)
    _size_window(window, avail)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
