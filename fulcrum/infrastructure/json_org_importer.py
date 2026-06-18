"""JSON importer that turns an org description into a starter blueprint.

The file is a JSON object mirroring the blueprint:
    {
      "teams": [
        {
          "id": "a", "name": "A", "has_local_authority": true,
          "incentive_skew": 0.2, "headcount": 8
        }
      ],
      "dependencies": [
        {"upstream": "a", "downstream": "b", "propagation_delay": 3}
      ],
      "workload": 5
    }
This matches the org section of a saved game, so the two formats stay aligned.
"""

from __future__ import annotations

import json
from pathlib import Path

from fulcrum.application.dto import DependencySpec, DomainSpec, OrgBlueprint, TeamSpec
from fulcrum.domain.errors import FulcrumError
from fulcrum.domain.models import DEFAULT_CATEGORY, DEFAULT_HEADCOUNT

_DEFAULT_WORKLOAD = 1
_DEFAULT_SKEW = 0.0
_DEFAULT_DELAY = 0
_DEFAULT_LEAD = ""
_DEFAULT_SIZE = 1
_DEFAULT_OWNER = ""


class OrgImportError(FulcrumError):
    """Raised when an org source cannot be parsed."""


def _optional_id(value) -> str | None:
    return None if value is None else str(value)


def _team(entry: dict) -> TeamSpec:
    try:
        return TeamSpec(
            id=str(entry["id"]),
            name=str(entry["name"]),
            has_local_authority=bool(entry["has_local_authority"]),
            incentive_skew=float(entry.get("incentive_skew", _DEFAULT_SKEW)),
            domain_id=_optional_id(entry.get("domain_id")),
            size=int(entry.get("size", _DEFAULT_SIZE)),
            owner=str(entry.get("owner", _DEFAULT_OWNER)),
            headcount=int(entry.get("headcount", DEFAULT_HEADCOUNT)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OrgImportError(f"invalid team entry: {entry}") from exc


def _domain(entry: dict) -> DomainSpec:
    try:
        return DomainSpec(
            id=str(entry["id"]),
            name=str(entry["name"]),
            parent_id=_optional_id(entry.get("parent_id")),
            lead=str(entry.get("lead", _DEFAULT_LEAD)),
            category=str(entry.get("category", DEFAULT_CATEGORY)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OrgImportError(f"invalid domain entry: {entry}") from exc


def _dependency(entry: dict) -> DependencySpec:
    try:
        return DependencySpec(
            upstream=str(entry["upstream"]),
            downstream=str(entry["downstream"]),
            propagation_delay=int(entry.get("propagation_delay", _DEFAULT_DELAY)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OrgImportError(f"invalid dependency entry: {entry}") from exc


def _parse_workload(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise OrgImportError(f"invalid workload: {value}") from exc


class JsonOrgImporter:
    """Builds an OrgBlueprint from a JSON org description."""

    def import_org(self, path: str) -> OrgBlueprint:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OrgImportError(f"could not read org file: {path}") from exc
        if not isinstance(data, dict):
            raise OrgImportError("org file must be a JSON object")
        teams = tuple(_team(entry) for entry in data.get("teams", ()))
        dependencies = tuple(
            _dependency(entry) for entry in data.get("dependencies", ())
        )
        domains = tuple(_domain(entry) for entry in data.get("domains", ()))
        workload = _parse_workload(data.get("workload", _DEFAULT_WORKLOAD))
        return OrgBlueprint(
            teams=teams,
            dependencies=dependencies,
            workload=workload,
            domains=domains,
        )
