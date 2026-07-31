"""Tests for the session autosave used to restore the last session."""

import json
from pathlib import Path

from fulcrum.application.dto import SessionSnapshot
from fulcrum.domain.models import OrgState, Origin, Team
from fulcrum.domain.moves import Move, MoveKind, apply_move
from fulcrum.infrastructure.json_serialization import org_to_dict
from fulcrum.infrastructure.org_autosave import FileOrgStore, default_autosave_path


def _org() -> OrgState:
    return OrgState(
        teams=(Team("a", "A", False, 0.2, owner="Priya Sharma"),),
        workload=4,
        origin=Origin.MODELLED,
    )


def _snapshot_with_history() -> SessionSnapshot:
    initial = _org()
    move = Move(MoveKind.DELEGATE_AUTHORITY, ("a",))
    return SessionSnapshot(initial, (move,), apply_move(initial, move))


def test_save_and_load_round_trip_without_history(tmp_path):
    store = FileOrgStore(tmp_path / "last_org.json")
    store.save(SessionSnapshot(_org(), (), _org()))
    assert store.load() == SessionSnapshot(_org(), (), _org())


def test_save_and_load_round_trip_with_history(tmp_path):
    store = FileOrgStore(tmp_path / "last_org.json")
    snapshot = _snapshot_with_history()
    store.save(snapshot)
    assert store.load() == snapshot


def test_top_level_stays_the_current_org_for_older_readers(tmp_path):
    path = tmp_path / "last_org.json"
    snapshot = _snapshot_with_history()
    FileOrgStore(path).save(snapshot)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["teams"][0]["has_local_authority"] is True
    assert data["initial_org"]["teams"][0]["has_local_authority"] is False


def test_legacy_org_only_file_loads_with_no_moves(tmp_path):
    path = tmp_path / "last_org.json"
    path.write_text(json.dumps(org_to_dict(_org())), encoding="utf-8")
    assert FileOrgStore(path).load() == SessionSnapshot(_org(), (), _org())


def test_unreadable_history_degrades_to_the_org_alone(tmp_path):
    path = tmp_path / "last_org.json"
    data = org_to_dict(_org())
    data["history"] = [{"kind": "not-a-kind", "targets": [], "label": ""}]
    data["initial_org"] = org_to_dict(_org())
    path.write_text(json.dumps(data), encoding="utf-8")
    assert FileOrgStore(path).load() == SessionSnapshot(_org(), (), _org())


def test_history_without_initial_org_degrades_to_the_org_alone(tmp_path):
    path = tmp_path / "last_org.json"
    data = org_to_dict(_org())
    data["history"] = [{"kind": "delegate_authority", "targets": ["a"], "label": ""}]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert FileOrgStore(path).load() == SessionSnapshot(_org(), (), _org())


def test_load_missing_file_returns_none(tmp_path):
    assert FileOrgStore(tmp_path / "absent.json").load() is None


def test_load_corrupt_json_returns_none(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("not json", encoding="utf-8")
    assert FileOrgStore(path).load() is None


def test_load_invalid_org_returns_none(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text(
        '{"teams": [], "dependencies": [], "workload": 1, "origin": "wizard"}',
        encoding="utf-8",
    )
    assert FileOrgStore(path).load() is None


def test_default_path_is_used_when_none_given(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert default_autosave_path() == tmp_path / ".fulcrum" / "last_org.json"
    store = FileOrgStore()
    store.save(SessionSnapshot(_org(), (), _org()))
    assert store.load() == SessionSnapshot(_org(), (), _org())
