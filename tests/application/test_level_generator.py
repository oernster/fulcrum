"""Tests for band-sized procedural generation."""

from random import Random

import pytest

from fulcrum.application.cluster_pool import reaches_great_move
from fulcrum.application.level_generator import _SHAPES, generate_level
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.hierarchy import (
    focused_suborg,
    headcount_in_domain,
    root_domains,
    total_headcount,
)
from fulcrum.domain.models import Origin, OrgState
from fulcrum.domain.org_size import ORG_SIZE_BANDS


def _band(key):
    return next(band for band in ORG_SIZE_BANDS if band.key == key)


def _leaf_ids(org):
    parents = {d.parent_id for d in org.domains if d.parent_id is not None}
    return tuple(d.id for d in org.domains if d.id not in parents)


def test_tiny_band_is_a_single_team_in_range():
    band = _band("tiny")
    org = generate_level(Random(0), band)
    assert isinstance(org, OrgState)
    assert org.origin == Origin.GENERATED
    assert org.domains == ()
    assert len(org.teams) == 1
    assert band.contains(total_headcount(org))


def test_headcount_rolls_up_from_teams():
    org = generate_level(Random(0), _band("medium"))
    assert total_headcount(org) == sum(t.headcount for t in org.teams)
    roots = root_domains(org)
    assert sum(headcount_in_domain(org, r.id) for r in roots) == total_headcount(org)
    assert all(headcount_in_domain(org, r.id) > 0 for r in roots)


def test_every_team_sits_in_a_leaf_domain():
    org = generate_level(Random(1), _band("medium"))
    leaves = set(_leaf_ids(org))
    assert all(t.domain_id in leaves for t in org.teams)


def test_drilled_sections_are_solvable():
    org = generate_level(Random(2), _band("small"))
    sim = DeterministicSimulator()
    for leaf in _leaf_ids(org):
        assert reaches_great_move(focused_suborg(org, leaf), sim)


def test_tier_categories_align_to_the_bottom():
    org = generate_level(Random(3), _band("medium"))
    by_id = {d.id: d for d in org.domains}
    roots = root_domains(org)
    assert len(roots) == 1
    assert roots[0].category == "Division"
    assert all(by_id[leaf].category == "Domain" for leaf in _leaf_ids(org))


@pytest.mark.parametrize("key", ["small", "medium", "large", "huge"])
def test_generated_org_lands_in_its_band(key):
    band = _band(key)
    org = generate_level(Random(5), band)
    assert band.contains(total_headcount(org))


def test_massive_band_generates_a_quarter_million_scale_org():
    band = _band("massive")
    org = generate_level(Random(5), band)
    assert band.contains(total_headcount(org))
    assert total_headcount(org) == sum(t.headcount for t in org.teams)


def test_shapes_cover_every_non_tiny_band():
    non_tiny = {band.key for band in ORG_SIZE_BANDS if band.key != "tiny"}
    assert set(_SHAPES) == non_tiny
