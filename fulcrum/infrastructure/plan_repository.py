"""File-based export and import of a plan: the JSON source and the HTML report.

The JSON captures the starting org and the move sequence, so a plan can be
re-imported and edited later; writes are atomic (temp file then replace). The
HTML report is written verbatim. Both are plain files the user chooses, distinct
from the slot-based save-game store.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fulcrum.application.dto import Plan
from fulcrum.infrastructure.json_save_repository import (
    move_from_dict,
    move_to_dict,
    org_from_dict,
    org_to_dict,
)

_JSON_INDENT = 2
_TMP_SUFFIX = ".tmp"


def plan_to_dict(plan: Plan) -> dict:
    return {
        "initial_org": org_to_dict(plan.initial_org),
        "moves": [move_to_dict(move) for move in plan.moves],
        "created_at": plan.created_at,
    }


def plan_from_dict(data: dict) -> Plan:
    return Plan(
        initial_org=org_from_dict(data["initial_org"]),
        moves=tuple(move_from_dict(move) for move in data["moves"]),
        created_at=data["created_at"],
    )


def write_plan(path: Path, plan: Plan) -> None:
    _atomic_write(path, json.dumps(plan_to_dict(plan), indent=_JSON_INDENT))


def read_plan(path: Path) -> Plan:
    return plan_from_dict(json.loads(path.read_text(encoding="utf-8")))


def write_html(path: Path, html: str) -> None:
    _atomic_write(path, html)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + _TMP_SUFFIX)
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
