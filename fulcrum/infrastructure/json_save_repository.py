"""JSON-backed save-game repository: local-first with atomic writes."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fulcrum.application.dto import SavedGame
from fulcrum.domain.models import (
    DEFAULT_CATEGORY,
    DEFAULT_HEADCOUNT,
    Dependency,
    Domain,
    Origin,
    OrgState,
    Team,
)
from fulcrum.domain.moves import Move, MoveKind

_SUFFIX = ".json"
_TMP_SUFFIX = ".tmp"
_JSON_INDENT = 2
_DEFAULT_SIZE = 1
_DEFAULT_OWNER = ""


def _team_to_dict(team: Team) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "has_local_authority": team.has_local_authority,
        "incentive_skew": team.incentive_skew,
        "domain_id": team.domain_id,
        "size": team.size,
        "owner": team.owner,
        "headcount": team.headcount,
    }


def _domain_to_dict(domain: Domain) -> dict:
    return {
        "id": domain.id,
        "name": domain.name,
        "parent_id": domain.parent_id,
        "lead": domain.lead,
        "category": domain.category,
    }


def _dependency_to_dict(dep: Dependency) -> dict:
    return {
        "upstream": dep.upstream,
        "downstream": dep.downstream,
        "propagation_delay": dep.propagation_delay,
    }


def org_to_dict(org: OrgState) -> dict:
    return {
        "teams": [_team_to_dict(t) for t in org.teams],
        "dependencies": [_dependency_to_dict(d) for d in org.dependencies],
        "workload": org.workload,
        "origin": org.origin.value,
        "domains": [_domain_to_dict(d) for d in org.domains],
    }


def move_to_dict(move: Move) -> dict:
    return {
        "kind": move.kind.value,
        "targets": list(move.targets),
        "label": move.label,
    }


def _saved_game_to_dict(game: SavedGame) -> dict:
    return {
        "org": org_to_dict(game.org),
        "history": [move_to_dict(m) for m in game.history],
        "created_at": game.created_at,
    }


def org_from_dict(data: dict) -> OrgState:
    teams = tuple(
        Team(
            t["id"],
            t["name"],
            t["has_local_authority"],
            t["incentive_skew"],
            t.get("domain_id"),
            t.get("size", _DEFAULT_SIZE),
            t.get("owner", _DEFAULT_OWNER),
            t.get("headcount", DEFAULT_HEADCOUNT),
        )
        for t in data["teams"]
    )
    dependencies = tuple(
        Dependency(d["upstream"], d["downstream"], d["propagation_delay"])
        for d in data["dependencies"]
    )
    domains = tuple(
        Domain(
            d["id"],
            d["name"],
            d.get("parent_id"),
            d.get("lead", ""),
            d.get("category", DEFAULT_CATEGORY),
        )
        for d in data.get("domains", ())
    )
    return OrgState(
        teams=teams,
        dependencies=dependencies,
        workload=data["workload"],
        origin=Origin(data["origin"]),
        domains=domains,
    )


def move_from_dict(data: dict) -> Move:
    return Move(MoveKind(data["kind"]), tuple(data["targets"]), data["label"])


def _saved_game_from_dict(data: dict) -> SavedGame:
    return SavedGame(
        org=org_from_dict(data["org"]),
        history=tuple(move_from_dict(m) for m in data["history"]),
        created_at=data["created_at"],
    )


class JsonSaveGameRepository:
    """Stores saved games as one JSON file per slot under a directory."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, slot: str, game: SavedGame) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._path(slot)
        tmp = path.with_name(path.name + _TMP_SUFFIX)
        tmp.write_text(
            json.dumps(_saved_game_to_dict(game), indent=_JSON_INDENT),
            encoding="utf-8",
        )
        os.replace(tmp, path)

    def load(self, slot: str) -> SavedGame:
        data = json.loads(self._path(slot).read_text(encoding="utf-8"))
        return _saved_game_from_dict(data)

    def slots(self) -> tuple[str, ...]:
        if not self._directory.exists():
            return ()
        return tuple(sorted(p.stem for p in self._directory.glob(f"*{_SUFFIX}")))

    def _path(self, slot: str) -> Path:
        return self._directory / f"{slot}{_SUFFIX}"
