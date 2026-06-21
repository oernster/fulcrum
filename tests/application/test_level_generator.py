"""Tests for deep, clustered procedural generation and its solvability."""

from pathlib import Path
from random import Random

from fulcrum.application.intake import build_org_state
from fulcrum.application.level_generator import (
    _DEPTH,
    _MIN_FANOUT,
    _MIN_PEOPLE,
    _ROOT_DIVISIONS,
    _build_hierarchy,
    _reaches_great_move,
    generate_level,
    has_great_move,
)
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.hierarchy import focused_suborg, total_headcount
from fulcrum.domain.models import Origin, OrgState, Team
from fulcrum.infrastructure.json_org_importer import JsonOrgImporter

_SEED_COUNT = 12
_ENTERPRISE = Path(__file__).resolve().parents[2] / "examples" / "org-3-enterprise.json"


def _enterprise():
    return build_org_state(
        JsonOrgImporter().import_org(str(_ENTERPRISE)), Origin.IMPORTED
    )


def _leaf_ids(org: OrgState) -> tuple[str, ...]:
    parents = {d.parent_id for d in org.domains if d.parent_id is not None}
    return tuple(d.id for d in org.domains if d.id not in parents)


def _tier_of(parent_of: dict, domain_id: str) -> int:
    tier = 1
    current = parent_of[domain_id]
    while current is not None:
        tier += 1
        current = parent_of[current]
    return tier


def _children_count(domains) -> dict:
    counts = {domain.id: 0 for domain in domains}
    for domain in domains:
        if domain.parent_id is not None:
            counts[domain.parent_id] += 1
    return counts


def test_generated_org_is_clustered_and_every_section_is_solvable():
    sim = DeterministicSimulator()
    for seed in range(_SEED_COUNT):
        org = generate_level(Random(seed))
        assert isinstance(org, OrgState)
        assert org.origin == Origin.GENERATED
        assert org.domains
        leaves = _leaf_ids(org)
        assert all(team.domain_id in leaves for team in org.teams)
        for leaf in leaves:
            assert _reaches_great_move(focused_suborg(org, leaf), sim)


def test_generated_org_nests_to_depth_and_branches():
    org = generate_level(Random(0))
    parent_of = {d.id: d.parent_id for d in org.domains}
    deepest = max(_tier_of(parent_of, did) for did in parent_of)
    assert deepest == _DEPTH
    counts = _children_count(org.domains)
    assert all(count == 0 or count >= _MIN_FANOUT for count in counts.values())


def test_generated_headcount_rolls_up_and_is_large():
    org = generate_level(Random(0))
    assert total_headcount(org) == sum(team.headcount for team in org.teams)
    assert total_headcount(org) >= len(org.teams) * _MIN_PEOPLE


def test_build_hierarchy_branches_and_reaches_the_depth():
    domains, leaf_ids = _build_hierarchy(Random(0), _DEPTH)
    parent_of = {d.id: d.parent_id for d in domains}
    parents = {p for p in parent_of.values() if p is not None}
    computed_leaves = {d.id for d in domains if d.id not in parents}
    assert computed_leaves == set(leaf_ids)
    assert all(_tier_of(parent_of, leaf) == _DEPTH for leaf in leaf_ids)
    roots = [d for d in domains if d.parent_id is None]
    assert len(roots) == _ROOT_DIVISIONS
    counts = _children_count(domains)
    assert all(count == 0 or count >= _MIN_FANOUT for count in counts.values())


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
