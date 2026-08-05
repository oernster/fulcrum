"""Tests for the session autosave used to restore the last session."""

import json
from pathlib import Path

from fulcrum.application.dto import SessionSnapshot
from fulcrum.domain.models import OrgState, Origin, Team
from fulcrum.domain.moves import Move, MoveKind, apply_move
from fulcrum.infrastructure.json_serialization import org_to_dict
from fulcrum.infrastructure.org_autosave import (
    _PRESERVE_ATTEMPTS,
    FileOrgStore,
    default_autosave_path,
    move_file,
)


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


# ------------------------------------------- the drilled section is remembered


def test_the_focused_section_round_trips(tmp_path):
    store = FileOrgStore(tmp_path / "last_org.json")
    store.save(SessionSnapshot(_org(), (), _org(), "unit"))
    restored = store.load()
    assert restored.focused_on == "unit"


def test_no_focus_is_written_at_all_when_there_is_none(tmp_path):
    path = tmp_path / "last_org.json"
    FileOrgStore(path).save(SessionSnapshot(_org(), (), _org()))
    assert "focused_on" not in json.loads(path.read_text(encoding="utf-8"))
    assert FileOrgStore(path).load().focused_on is None


def test_a_file_written_before_the_focus_existed_loads_unfocused(tmp_path):
    path = tmp_path / "last_org.json"
    path.write_text(json.dumps(org_to_dict(_org())), encoding="utf-8")
    assert FileOrgStore(path).load().focused_on is None


def test_a_focus_that_is_not_a_name_is_ignored(tmp_path):
    # A hand-edited file must not be able to put a non-name into the session.
    path = tmp_path / "last_org.json"
    data = org_to_dict(_org())
    data["focused_on"] = {"not": "a name"}
    path.write_text(json.dumps(data), encoding="utf-8")
    assert FileOrgStore(path).load().focused_on is None


def test_the_focus_survives_history_that_will_not_parse(tmp_path):
    path = tmp_path / "last_org.json"
    data = org_to_dict(_org())
    data["history"] = [{"kind": "not-a-kind", "targets": [], "label": ""}]
    data["initial_org"] = org_to_dict(_org())
    data["focused_on"] = "unit"
    path.write_text(json.dumps(data), encoding="utf-8")
    restored = FileOrgStore(path).load()
    assert restored.moves == ()
    assert restored.focused_on == "unit"


# ------------------------------------------------- never destroy what we find


def test_a_clean_store_reports_nothing_preserved_and_is_not_sealed(tmp_path):
    store = FileOrgStore(tmp_path / "last_org.json")
    assert store.preserved_copy is None
    assert store.is_sealed is False


def test_an_unreadable_file_is_kept_rather_than_overwritten(tmp_path):
    # The regression this guards: load fails, the app starts a fresh session
    # and saves it, and the previous organisation is gone within seconds.
    path = tmp_path / "last_org.json"
    path.write_text("not json", encoding="utf-8")
    store = FileOrgStore(path)
    assert store.load() is None
    kept = store.preserved_copy
    assert kept is not None and kept.read_text(encoding="utf-8") == "not json"
    assert not path.exists()
    store.save(SessionSnapshot(_org(), (), _org()))
    assert store.load() == SessionSnapshot(_org(), (), _org())
    assert kept.read_text(encoding="utf-8") == "not json"


def test_a_second_bad_launch_does_not_overwrite_the_first_rescue(tmp_path):
    path = tmp_path / "last_org.json"
    path.write_text("first", encoding="utf-8")
    first = FileOrgStore(path)
    first.load()
    path.write_text("second", encoding="utf-8")
    second = FileOrgStore(path)
    second.load()
    assert first.preserved_copy != second.preserved_copy
    assert first.preserved_copy.read_text(encoding="utf-8") == "first"
    assert second.preserved_copy.read_text(encoding="utf-8") == "second"


def test_the_store_seals_when_there_is_no_free_name_to_preserve_under(tmp_path):
    path = tmp_path / "last_org.json"
    path.write_text("not json", encoding="utf-8")
    for attempt in range(_PRESERVE_ATTEMPTS):
        suffix = ".unreadable" if attempt == 0 else f".unreadable{attempt}"
        path.with_name(path.name + suffix).write_text("taken", encoding="utf-8")
    store = FileOrgStore(path)
    assert store.load() is None
    assert store.is_sealed is True
    assert store.preserved_copy is None
    store.save(SessionSnapshot(_org(), (), _org()))
    assert path.read_text(encoding="utf-8") == "not json"


def test_the_store_seals_when_the_file_is_present_but_will_not_open(tmp_path):
    # A directory where the file should be: present, so not a clean start,
    # and unreadable in a way no rename can rescue.
    path = tmp_path / "last_org.json"
    path.mkdir()
    store = FileOrgStore(path)
    assert store.load() is None
    assert store.is_sealed is True
    store.save(SessionSnapshot(_org(), (), _org()))
    assert path.is_dir()


def test_moving_a_file_reports_failure_instead_of_raising(tmp_path):
    assert move_file(tmp_path / "absent", tmp_path / "target") is False
    source = tmp_path / "present"
    source.write_text("x", encoding="utf-8")
    assert move_file(source, tmp_path / "moved") is True
    assert (tmp_path / "moved").read_text(encoding="utf-8") == "x"


def test_default_path_is_used_when_none_given(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert default_autosave_path() == tmp_path / ".fulcrum" / "last_org.json"
    store = FileOrgStore()
    store.save(SessionSnapshot(_org(), (), _org()))
    assert store.load() == SessionSnapshot(_org(), (), _org())
