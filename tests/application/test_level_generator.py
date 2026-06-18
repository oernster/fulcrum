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


def _org_from(domains, domain_of, count):
    teams = tuple(
        Team(f"team_{i + 1}", f"Team {i + 1}", i == 0, domain_id=domain_of[i])
        for i in range(count)
    )
    return OrgState(teams=teams, domains=domains)


def test_medium_orgs_nest_departments_under_divisions():
    domains, domain_of = _build_domains(Random(0), 8)
    roots = [d for d in domains if d.parent_id is None]
    leaves = [d for d in domains if d.parent_id is not None]
    assert len(roots) == 2
    assert len(leaves) == 4
    assert all(d.category == GROUP_CATEGORIES[0] for d in roots)
    assert all(d.category == GROUP_CATEGORIES[1] for d in leaves)
    root_ids = {d.id for d in roots}
    assert all(d.parent_id in root_ids for d in leaves)
    leaf_ids = {d.id for d in leaves}
    assert all(assigned in leaf_ids for assigned in domain_of)
    assert len(_org_from(domains, domain_of, 8).domains) == 6


def test_large_orgs_nest_three_tiers():
    domains, domain_of = _build_domains(Random(1), 12)
    assert len(domains) == 14
    parents = {d.parent_id for d in domains if d.parent_id is not None}
    leaf_ids = {d.id for d in domains if d.id not in parents}
    assert len(leaf_ids) == 8
    tiers = {d.category for d in domains}
    assert {GROUP_CATEGORIES[0], GROUP_CATEGORIES[1], GROUP_CATEGORIES[2]} <= tiers
    assert all(assigned in leaf_ids for assigned in domain_of)
    assert len(_org_from(domains, domain_of, 12).domains) == 14
