"""Tests for legacy origin migration in the shared JSON serialization."""

import pytest

from fulcrum.domain.models import OrgState, Origin, Team
from fulcrum.infrastructure.json_serialization import org_from_dict, org_to_dict


def _data(origin: str) -> dict:
    data = org_to_dict(OrgState(teams=(Team("a", "A", True),)))
    data["origin"] = origin
    return data


def test_a_legacy_wizard_file_loads_as_modelled():
    assert org_from_dict(_data("wizard")).origin is Origin.MODELLED


def test_an_unknown_origin_still_fails():
    with pytest.raises(ValueError):
        org_from_dict(_data("teleported"))
