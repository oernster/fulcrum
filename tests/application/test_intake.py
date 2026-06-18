"""Tests for the blueprint-to-OrgState intake compiler."""

import pytest

from fulcrum.application.dto import (
    DependencySpec,
    DomainSpec,
    OrgBlueprint,
    TeamSpec,
)
from fulcrum.application.intake import build_org_state
from fulcrum.domain.errors import InvalidOrgStateError
from fulcrum.domain.models import Origin


def test_build_org_state_valid():
    blueprint = OrgBlueprint(
        teams=(TeamSpec("a", "A", True, 0.1), TeamSpec("b", "B", False, 0.4)),
        dependencies=(DependencySpec("a", "b", 2),),
        workload=4,
    )
    org = build_org_state(blueprint, Origin.WIZARD)
    assert org.origin == Origin.WIZARD
    assert org.team_ids == ("a", "b")
    assert org.dependencies[0].propagation_delay == 2


def test_build_org_state_invalid_propagates():
    blueprint = OrgBlueprint(
        teams=(TeamSpec("a", "A", True), TeamSpec("a", "A2", False)),
    )
    with pytest.raises(InvalidOrgStateError):
        build_org_state(blueprint, Origin.IMPORTED)


def test_build_org_state_with_domains():
    blueprint = OrgBlueprint(
        teams=(TeamSpec("a", "A", True, 0.0, domain_id="core"),),
        domains=(
            DomainSpec("core", "Core"),
            DomainSpec("pay", "Payments", parent_id="core", lead="Dana"),
        ),
    )
    org = build_org_state(blueprint, Origin.WIZARD)
    assert org.team("a").domain_id == "core"
    assert tuple(d.id for d in org.domains) == ("core", "pay")
    assert org.domains[1].lead == "Dana"
