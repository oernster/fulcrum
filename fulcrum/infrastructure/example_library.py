"""The example library: bundled calibration organisations, loadable in-app.

The calibration cases under examples/calibration/ double as example
organisations the user can open from the File menu, inspect on the board and
rework in the editor. Each case's calibration block supplies its display
label and the one-line note shown beside it; the org itself loads through
the same serialization the importer uses, so an opened example behaves
exactly like an imported organisation. Implements the application's
ExampleSource Protocol.
"""

from __future__ import annotations

import json
from pathlib import Path

from fulcrum.application.dto import ExampleSummary
from fulcrum.domain.models import OrgState
from fulcrum.infrastructure.json_serialization import org_from_dict

_TEMPLATE_NAME = "TEMPLATE.json"
_CALIBRATION_KEY = "calibration"
_LABEL_KEY = "label"
_NOTE_KEY = "note"


class FileExampleLibrary:
    """Example organisations discovered from a directory of calibration JSON."""

    def __init__(self, directory: Path | None) -> None:
        self._directory = directory

    def examples(self) -> tuple[ExampleSummary, ...]:
        """The loadable examples, sorted by label.

        The template is skipped, as is any file without a calibration block
        or with unreadable JSON: the menu should never offer an entry that
        cannot load. A missing directory simply yields no examples.
        """
        if self._directory is None or not self._directory.is_dir():
            return ()
        summaries: list[ExampleSummary] = []
        for path in sorted(self._directory.glob("*.json")):
            if path.name == _TEMPLATE_NAME:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            meta = data.get(_CALIBRATION_KEY)
            if not isinstance(meta, dict) or _LABEL_KEY not in meta:
                continue
            summaries.append(
                ExampleSummary(
                    key=str(path),
                    label=str(meta[_LABEL_KEY]),
                    note=str(meta.get(_NOTE_KEY, "")),
                )
            )
        return tuple(sorted(summaries, key=lambda summary: summary.label))

    def load(self, key: str) -> OrgState:
        """Load one example's organisation, exactly as the importer would."""
        data = json.loads(Path(key).read_text(encoding="utf-8"))
        return org_from_dict(data)
