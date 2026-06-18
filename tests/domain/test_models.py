"""Tests for the core organisational value objects."""

import pytest

from fulcrum.domain.errors import InvalidOrgStateError, UnknownTeamError
from fulcrum.domain.models import Dependency, Domain, Origin, OrgState, Team


def _team(team_id="a", authority=True, skew=0.0):
    return Team(
        id=team_id,
        name=team_id.upper(),
        has_local_authority=authority,
        incentive_skew=skew,
    )


def test_team_valid_and_copies():
    team = _team("a", authority=False, skew=0.2)
    assert team.has_local_authority is False
    assert team.with_authority(True).has_local_authority is True
    assert team.with_incentive_skew(0.5).incentive_skew == 0.5


@pytest.mark.parametrize(
    "kwargs",
    [
        {"id": "", "name": "A", "has_local_authority": True},
        {"id": "a", "name": "", "has_local_authority": True},
        {"id": "a", "name": "A", "has_local_authority": True, "incentive_skew": -0.1},
        {"id": "a", "name": "A", "has_local_authority": True, "incentive_skew": 1.1},
    ],
)
def test_team_invalid(kwargs):
    with pytest.raises(InvalidOrgStateError):
        Team(**kwargs)


def test_dependency_valid_and_helpers():
    dep = Dependency("a", "b", 2)
    assert dep.touches("a") and dep.touches("b")
    assert not dep.touches("c")
    assert dep.with_delay(5).propagation_delay == 5


@pytest.mark.parametrize(
    "args",
    [("", "b", 0), ("a", "", 0), ("a", "a", 0), ("a", "b", -1)],
)
def test_dependency_invalid(args):
    with pytest.raises(InvalidOrgStateError):
        Dependency(*args)


def test_origin_values():
    assert Origin.GENERATED.value == "generated"
    assert Origin.IMPORTED.value == "imported"
    assert Origin.WIZARD.value == "wizard"


def test_org_state_valid_accessors():
    org = OrgState(
        teams=(_team("a"), _team("b")),
        dependencies=(Dependency("a", "b", 1),),
        workload=3,
        origin=Origin.WIZARD,
    )
    assert org.team_ids == ("a", "b")
    assert org.team("a").id == "a"
    assert org.has_team("b") is True
    assert org.has_team("z") is False


def test_org_state_team_unknown_raises():
    org = OrgState(teams=(_team("a"),))
    with pytest.raises(UnknownTeamError):
        org.team("z")


@pytest.mark.parametrize(
    "factory",
    [
        lambda: OrgState(teams=()),
        lambda: OrgState(teams=(_team("a"), _team("a"))),
        lambda: OrgState(teams=(_team("a"),), dependencies=(Dependency("a", "z"),)),
        lambda: OrgState(teams=(_team("a"),), workload=0),
    ],
)
def test_org_state_invalid(factory):
    with pytest.raises(InvalidOrgStateError):
        factory()


def test_domain_valid_and_defaults():
    domain = Domain("d1", "Platform")
    assert domain.parent_id is None
    assert domain.lead == ""
    nested = Domain("d2", "Payments", parent_id="d1", lead="Dana")
    assert nested.parent_id == "d1"
    assert nested.lead == "Dana"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"id": "", "name": "D"},
        {"id": "d", "name": ""},
        {"id": "d", "name": "D", "parent_id": "d"},
    ],
)
def test_domain_invalid(kwargs):
    with pytest.raises(InvalidOrgStateError):
        Domain(**kwargs)


def test_team_copies_preserve_domain_id():
    team = Team("a", "A", False, 0.2, domain_id="d1")
    assert team.with_authority(True).domain_id == "d1"
    assert team.with_incentive_skew(0.5).domain_id == "d1"


def test_team_size_and_owner_validation_and_copies():
    team = Team("a", "A", True, 0.0, domain_id="d1", size=4, owner="Ada")
    assert team.size == 4
    assert team.owner == "Ada"
    assert team.with_size(2).size == 2
    assert team.with_size(2).owner == "Ada"
    assert team.with_authority(False).owner == "Ada"
    assert team.with_incentive_skew(0.5).owner == "Ada"
    with pytest.raises(InvalidOrgStateError):
        Team("a", "A", True, 0.0, size=0)


def test_org_state_valid_hierarchy():
    org = OrgState(
        teams=(_team("a"), Team("b", "B", True, 0.0, domain_id="sub")),
        domains=(Domain("root", "Root"), Domain("sub", "Sub", parent_id="root")),
    )
    assert org.team("b").domain_id == "sub"
    assert len(org.domains) == 2


@pytest.mark.parametrize(
    "factory",
    [
        lambda: OrgState(
            teams=(_team("a"),),
            domains=(Domain("d", "D"), Domain("d", "D2")),
        ),
        lambda: OrgState(teams=(Team("a", "A", True, 0.0, domain_id="missing"),)),
        lambda: OrgState(
            teams=(_team("a"),),
            domains=(Domain("d", "D", parent_id="missing"),),
        ),
        lambda: OrgState(
            teams=(_team("a"),),
            domains=(
                Domain("x", "X", parent_id="y"),
                Domain("y", "Y", parent_id="x"),
            ),
        ),
    ],
)
def test_org_state_invalid_domains(factory):
    with pytest.raises(InvalidOrgStateError):
        factory()
