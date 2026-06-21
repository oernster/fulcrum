"""Tests for the JSON save-game repository."""

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
from fulcrum.infrastructure.json_save_repository import (
    JsonSaveGameRepository,
    org_from_dict,
)


def _saved_game():
    org = OrgState(
        teams=(
            Team("a", "A", True, 0.1, domain_id="core", size=2, owner="Ada"),
            Team("b", "B", False, 0.4, domain_id="core"),
        ),
        dependencies=(Dependency("a", "b", 3),),
        workload=4,
        origin=Origin.WIZARD,
        domains=(Domain("core", "Core", lead="Dana", headcount=1200),),
    )
    return SavedGame(
        org=org,
        history=(Move(MoveKind.DELEGATE_AUTHORITY, ("b",)),),
        created_at="2026-06-17T00:00:00",
    )


def test_save_load_roundtrip_and_slots(tmp_path):
    repository = JsonSaveGameRepository(tmp_path / "saves")
    assert repository.slots() == ()
    game = _saved_game()
    repository.save("slot1", game)
    assert repository.slots() == ("slot1",)
    loaded = repository.load("slot1")
    assert loaded.org == game.org
    assert loaded.org.domains == game.org.domains
    assert loaded.org.domains[0].headcount == 1200
    assert loaded.org.team("a").domain_id == "core"
    assert loaded.org.team("a").size == 2
    assert loaded.org.team("a").owner == "Ada"
    assert loaded.history == game.history
    assert loaded.created_at == game.created_at


def test_save_load_roundtrips_domain_category(tmp_path):
    repository = JsonSaveGameRepository(tmp_path / "saves")
    repository.save("slot1", _saved_game())
    loaded = repository.load("slot1")
    assert loaded.org.domains[0].category == DEFAULT_CATEGORY


def test_org_from_dict_defaults_a_missing_category():
    data = {
        "teams": [
            {
                "id": "a",
                "name": "A",
                "has_local_authority": True,
                "incentive_skew": 0.0,
            }
        ],
        "dependencies": [],
        "workload": 1,
        "origin": "wizard",
        "domains": [{"id": "d", "name": "D"}],
    }
    assert org_from_dict(data).domains[0].category == DEFAULT_CATEGORY


def test_save_load_roundtrips_headcount(tmp_path):
    repository = JsonSaveGameRepository(tmp_path / "saves")
    org = OrgState(teams=(Team("a", "A", True, 0.0, headcount=1500),), workload=1)
    repository.save("s", SavedGame(org=org, history=(), created_at="t"))
    assert repository.load("s").org.team("a").headcount == 1500


def test_org_from_dict_defaults_a_missing_headcount():
    data = {
        "teams": [
            {
                "id": "a",
                "name": "A",
                "has_local_authority": True,
                "incentive_skew": 0.0,
            }
        ],
        "dependencies": [],
        "workload": 1,
        "origin": "wizard",
        "domains": [],
    }
    assert org_from_dict(data).team("a").headcount == DEFAULT_HEADCOUNT
