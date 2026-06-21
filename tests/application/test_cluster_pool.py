"""Tests for the solvable cluster pool and its cloning across leaves."""

from pathlib import Path
from random import Random

from fulcrum.application.cluster_pool import (
    _BIG_TEAM_MAX,
    _BIG_TEAM_MIN,
    _POOL_SIZE_CAP,
    _TEAM_MAX,
    _TEAM_MIN,
    _team_headcount,
    assemble_clusters,
    build_cluster_pool,
    clone_cluster,
    has_great_move,
    pick_workload,
    reaches_great_move,
)
from fulcrum.application.intake import build_org_state
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Domain, Origin, OrgState, Team
from fulcrum.infrastructure.json_org_importer import JsonOrgImporter

_MIN_WORKLOAD = 6
_MAX_WORKLOAD = 9
_ENTERPRISE = Path(__file__).resolve().parents[2] / "examples" / "org-3-enterprise.json"


def _enterprise():
    return build_org_state(
        JsonOrgImporter().import_org(str(_ENTERPRISE)), Origin.IMPORTED
    )


def _healthy():
    return OrgState(
        teams=(Team("a", "A", True, 0.0), Team("b", "B", True, 0.0)),
        workload=1,
    )


def _section(teams, deps, workload):
    return OrgState(
        teams=teams, dependencies=deps, workload=workload, origin=Origin.GENERATED
    )


def test_pick_workload_stays_in_range():
    workloads = {pick_workload(Random(seed)) for seed in range(20)}
    assert all(_MIN_WORKLOAD <= w <= _MAX_WORKLOAD for w in workloads)


def test_team_headcount_stays_team_sized():
    rng = Random(0)
    sizes = {_team_headcount(rng) for _ in range(500)}
    assert min(sizes) >= _TEAM_MIN
    assert max(sizes) <= _BIG_TEAM_MAX
    assert all(size <= _TEAM_MAX or size >= _BIG_TEAM_MIN for size in sizes)


def test_has_great_move_false_for_healthy_org():
    assert has_great_move(_healthy(), DeterministicSimulator()) is False


def test_reaches_a_great_move_after_setup_moves():
    org = _enterprise()
    sim = DeterministicSimulator()
    assert not has_great_move(org, sim)
    assert reaches_great_move(org, sim)


def test_no_great_move_reachable_without_lookahead():
    org = _enterprise()
    assert reaches_great_move(org, DeterministicSimulator(), lookahead=0) is False


def test_reaches_great_move_false_for_healthy_org():
    assert reaches_great_move(_healthy(), DeterministicSimulator()) is False


def test_pool_templates_are_each_solvable():
    rng = Random(1)
    sim = DeterministicSimulator()
    workload = pick_workload(rng)
    pool = build_cluster_pool(rng, sim, workload, leaf_count=5)
    assert len(pool) == 5
    for teams, deps in pool:
        assert reaches_great_move(_section(teams, deps, workload), sim)


def test_pool_is_capped_for_a_large_leaf_count():
    rng = Random(2)
    sim = DeterministicSimulator()
    workload = pick_workload(rng)
    pool = build_cluster_pool(rng, sim, workload, leaf_count=10_000)
    assert len(pool) == _POOL_SIZE_CAP


def test_clone_preserves_structure_with_fresh_identity():
    rng = Random(3)
    sim = DeterministicSimulator()
    workload = pick_workload(rng)
    template = build_cluster_pool(rng, sim, workload, leaf_count=1)[0]
    template_teams, template_deps = template
    teams, deps = clone_cluster(template, rng, "leaf", start_index=100)
    assert [t.has_local_authority for t in teams] == [
        t.has_local_authority for t in template_teams
    ]
    assert [t.incentive_skew for t in teams] == [
        t.incentive_skew for t in template_teams
    ]
    assert [d.propagation_delay for d in deps] == [
        d.propagation_delay for d in template_deps
    ]
    assert all(t.domain_id == "leaf" for t in teams)
    assert {t.id for t in teams}.isdisjoint({t.id for t in template_teams})
    leaf_section = OrgState(
        teams=teams,
        dependencies=deps,
        workload=workload,
        origin=Origin.GENERATED,
        domains=(Domain("leaf", "Leaf"),),
    )
    assert reaches_great_move(leaf_section, sim)


def _leaf_of(teams, team_id):
    return next(t.domain_id for t in teams if t.id == team_id)


def test_assemble_tags_leaves_and_links_clusters_in_a_chain():
    rng = Random(4)
    sim = DeterministicSimulator()
    workload = pick_workload(rng)
    leaf_ids = ("l1", "l2", "l3")
    pool = build_cluster_pool(rng, sim, workload, leaf_count=len(leaf_ids))
    teams, deps = assemble_clusters(rng, pool, leaf_ids)
    assert {t.domain_id for t in teams} == set(leaf_ids)
    assert len({t.id for t in teams}) == len(teams)
    cross = [
        d for d in deps if _leaf_of(teams, d.upstream) != _leaf_of(teams, d.downstream)
    ]
    assert len(cross) == len(leaf_ids) - 1
