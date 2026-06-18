"""Tests for procedural level generation and its solvability guarantee."""

from pathlib import Path
from random import Random

from fulcrum.application.intake import build_org_state
from fulcrum.application.level_generator import (
    _build_domains,
    _reaches_great_move,
    generate_level,
    has_great_move,
)
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import GROUP_CATEGORIES, Origin, OrgState, Team
from fulcrum.infrastructure.json_org_importer import JsonOrgImporter

_SEED_COUNT = 12
_ENTERPRISE = Path(__file__).resolve().parents[2] / "examples" / "org-3-enterprise.json"


def _enterprise():
    return build_org_state(
        JsonOrgImporter().import_org(str(_ENTERPRISE)), Origin.IMPORTED
    )


def test_generate_level_is_valid_and_solvable():
    for seed in range(_SEED_COUNT):
        org = generate_level(Random(seed))
        assert isinstance(org, OrgState)
        assert org.origin == Origin.GENERATED
        assert org.domains
        assert _reaches_great_move(org, DeterministicSimulator())


def test_has_great_move_false_for_healthy_org():
    healthy = OrgState(
        teams=(Team("a", "A", True, 0.0), Team("b", "B", True, 0.0)),
        workload=1,
    )
    assert has_great_move(healthy, DeterministicSimulator()) is False


def test_reaches_a_great_move_after_setup_moves():
    org = _enterprise()
    sim = DeterministicSimulator()
    assert not has_great_move(org, sim)
    assert _reaches_great_move(org, sim)


def test_no_great_move_reachable_without_lookahead():
    org = _enterprise()
    assert _reaches_great_move(org, DeterministicSimulator(), lookahead=0) is False


def test_reaches_great_move_false_for_healthy_org():
    healthy = OrgState(
        teams=(Team("a", "A", True, 0.0), Team("b", "B", True, 0.0)),
        workload=1,
    )
    assert _reaches_great_move(healthy, DeterministicSimulator()) is False


def test_orgs_group_into_root_domains():
    domains, domain_of = _build_domains(Random(0), 4)
    assert len(domains) == 2
    assert all(domain.parent_id is None for domain in domains)
    assert all(domain.category == GROUP_CATEGORIES[0] for domain in domains)
    known = {domain.id for domain in domains}
    assert all(assigned in known for assigned in domain_of)


def test_largest_orgs_nest_a_subdomain():
    domains, domain_of = _build_domains(Random(0), 8)
    nested = [domain for domain in domains if domain.parent_id is not None]
    assert len(nested) == 1
    assert nested[0].parent_id == "domain_1"
    assert nested[0].category == GROUP_CATEGORIES[1]
    # The grouping must build a valid org: construction validates the domains.
    teams = tuple(
        Team(f"team_{i + 1}", f"Team {i + 1}", i == 0, domain_id=domain_of[i])
        for i in range(8)
    )
    org = OrgState(teams=teams, domains=domains)
    assert len(org.domains) == 3
