"""Tests for the current-org autosave used to restore the last session."""

from pathlib import Path

from fulcrum.domain.models import Origin, OrgState, Team
from fulcrum.infrastructure.org_autosave import FileOrgStore, default_autosave_path


def _org() -> OrgState:
    return OrgState(
        teams=(Team("a", "A", True, 0.2, owner="Priya Sharma"),),
        workload=4,
        origin=Origin.WIZARD,
    )


def test_save_and_load_round_trip(tmp_path):
    store = FileOrgStore(tmp_path / "last_org.json")
    store.save(_org())
    assert store.load() == _org()


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
    store.save(_org())
    assert store.load() == _org()
