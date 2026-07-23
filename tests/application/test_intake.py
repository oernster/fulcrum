"""Tests for the blueprint-to-OrgState intake compiler."""

import pytest

from fulcrum.application.dto import (
    DependencySpec,
    DomainSpec,
    OrgBlueprint,
    TeamSpec,
)
from fulcrum.application.intake import build_org_state, org_to_blueprint
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


def test_build_org_state_carries_headcount():
    blueprint = OrgBlueprint(teams=(TeamSpec("a", "A", True, 0.0, headcount=300),))
    org = build_org_state(blueprint, Origin.WIZARD)
    assert org.team("a").headcount == 300


def test_build_org_state_carries_domain_headcount():
    blueprint = OrgBlueprint(
        teams=(TeamSpec("a", "A", True, 0.0, domain_id="core"),),
        domains=(DomainSpec("core", "Core", headcount=120),),
    )
    org = build_org_state(blueprint, Origin.IMPORTED)
    assert org.domains[0].headcount == 120


def test_org_to_blueprint_inverts_build_org_state():
    blueprint = OrgBlueprint(
        teams=(
            TeamSpec(
                "a",
                "A",
                True,
                0.25,
                domain_id="core",
                size=3,
                owner="Priya Sharma",
                headcount=9,
            ),
            TeamSpec("b", "B", False, 0.4),
        ),
        dependencies=(DependencySpec("a", "b", 2),),
        workload=7,
        domains=(
            DomainSpec(
                "core",
                "Core",
                lead="Kwame Mensah",
                category="Division",
                headcount=40,
            ),
        ),
    )
    org = build_org_state(blueprint, Origin.WIZARD)
    rebuilt = build_org_state(org_to_blueprint(org), Origin.WIZARD)
    assert rebuilt == org
