"""Tests for the file-backed preferences store."""

import json

from fulcrum.infrastructure.settings_store import (
    FileSettingsStore,
    default_settings_path,
)


def test_round_trips_the_theme(tmp_path):
    store = FileSettingsStore(tmp_path / "settings.json")
    store.save_theme("light")
    assert store.load_theme() == "light"
    store.save_theme("dark")
    assert store.load_theme() == "dark"


def test_missing_broken_or_unknown_degrades_to_dark(tmp_path):
    assert FileSettingsStore(tmp_path / "absent.json").load_theme() == "dark"
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert FileSettingsStore(broken).load_theme() == "dark"
    listy = tmp_path / "listy.json"
    listy.write_text("[1, 2]", encoding="utf-8")
    assert FileSettingsStore(listy).load_theme() == "dark"
    odd = tmp_path / "odd.json"
    odd.write_text(json.dumps({"theme": "neon"}), encoding="utf-8")
    assert FileSettingsStore(odd).load_theme() == "dark"


def test_saving_preserves_unrelated_keys(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"future": 7}), encoding="utf-8")
    store = FileSettingsStore(path)
    store.save_theme("light")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"future": 7, "theme": "light"}


def test_saving_over_a_broken_file_starts_fresh(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[]", encoding="utf-8")
    store = FileSettingsStore(path)
    store.save_theme("light")
    assert json.loads(path.read_text(encoding="utf-8")) == {"theme": "light"}


def test_default_path_is_per_user():
    path = default_settings_path()
    assert path.name == "settings.json"
    assert path.parent.name == ".fulcrum"
