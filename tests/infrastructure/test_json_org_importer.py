"""Tests for the JSON org importer."""

import json

import pytest

from fulcrum.domain.models import DEFAULT_HEADCOUNT
from fulcrum.infrastructure.json_org_importer import JsonOrgImporter, OrgImportError


def _write(tmp_path, payload):
    path = tmp_path / "org.json"
    text = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_import_valid(tmp_path):
    payload = {
        "teams": [
            {
                "id": "a",
                "name": "Team A",
                "has_local_authority": True,
                "incentive_skew": 0.1,
            },
            {"id": "b", "name": "Team B", "has_local_authority": False},
        ],
        "dependencies": [{"upstream": "a", "downstream": "b", "propagation_delay": 3}],
        "workload": 5,
    }
    blueprint = JsonOrgImporter().import_org(_write(tmp_path, payload))
    assert tuple(t.id for t in blueprint.teams) == ("a", "b")
    assert blueprint.teams[1].has_local_authority is False
    assert blueprint.teams[1].incentive_skew == 0.0
    assert blueprint.dependencies[0].propagation_delay == 3
    assert blueprint.workload == 5


def test_import_unreadable_json(tmp_path):
    with pytest.raises(OrgImportError):
        JsonOrgImporter().import_org(_write(tmp_path, "{not valid json"))


def test_import_non_object_root(tmp_path):
    with pytest.raises(OrgImportError):
        JsonOrgImporter().import_org(_write(tmp_path, "[]"))


def test_import_bad_team(tmp_path):
    with pytest.raises(OrgImportError):
        JsonOrgImporter().import_org(_write(tmp_path, {"teams": [{"name": "x"}]}))


def test_import_bad_dependency(tmp_path):
    with pytest.raises(OrgImportError):
        JsonOrgImporter().import_org(
            _write(tmp_path, {"teams": [], "dependencies": [{"upstream": "a"}]})
        )


def test_import_bad_workload(tmp_path):
    with pytest.raises(OrgImportError):
        JsonOrgImporter().import_org(_write(tmp_path, {"workload": "lots"}))


def test_import_with_domains(tmp_path):
    payload = {
        "teams": [
            {
                "id": "a",
                "name": "A",
                "has_local_authority": True,
                "domain_id": "core",
            }
        ],
        "domains": [
            {"id": "core", "name": "Core"},
            {"id": "pay", "name": "Payments", "parent_id": "core", "lead": "Dana"},
        ],
        "workload": 3,
    }
    blueprint = JsonOrgImporter().import_org(_write(tmp_path, payload))
    assert blueprint.teams[0].domain_id == "core"
    assert tuple(d.id for d in blueprint.domains) == ("core", "pay")
    assert blueprint.domains[1].parent_id == "core"
    assert blueprint.domains[1].lead == "Dana"


def test_import_bad_domain(tmp_path):
    with pytest.raises(OrgImportError):
        JsonOrgImporter().import_org(_write(tmp_path, {"domains": [{"name": "x"}]}))


def test_import_reads_and_defaults_headcount(tmp_path):
    payload = {
        "teams": [
            {"id": "a", "name": "A", "has_local_authority": True, "headcount": 250},
            {"id": "b", "name": "B", "has_local_authority": False},
        ],
        "workload": 1,
    }
    blueprint = JsonOrgImporter().import_org(_write(tmp_path, payload))
    assert blueprint.teams[0].headcount == 250
    assert blueprint.teams[1].headcount == DEFAULT_HEADCOUNT
