"""Tests for the bulk population table."""

from fulcrum.domain import hierarchy
from fulcrum.domain.models import Domain, OrgState, Team
from fulcrum.domain.populations import headcounts_by_domain


def test_bulk_headcounts_match_the_per_domain_walk():
    """The one-pass table agrees with headcount_in_domain for every domain.

    Covers both population sources: units carrying their own headcounts
    (which win) and units priced from their teams, nested either way.
    """
    from_teams = OrgState(
        teams=(
            Team("a", "A", True, 0.0, domain_id="plat", headcount=10),
            Team("b", "B", True, 0.0, domain_id="pay", headcount=20),
            Team("c", "C", True, 0.0, domain_id="cards", headcount=5),
        ),
        workload=1,
        domains=(
            Domain("plat", "Platform"),
            Domain("pay", "Payments", parent_id="plat"),
            Domain("cards", "Cards", parent_id="pay"),
            Domain("empty", "Empty"),
        ),
    )
    from_units = OrgState(
        teams=(Team("a", "A", True, 0.0, domain_id="pay", headcount=1),),
        workload=1,
        domains=(
            Domain("plat", "Platform", headcount=300),
            Domain("pay", "Payments", parent_id="plat", headcount=120),
        ),
    )
    for org in (from_teams, from_units):
        table = headcounts_by_domain(org)
        assert set(table) == {d.id for d in org.domains}
        for domain in org.domains:
            assert table[domain.id] == hierarchy.headcount_in_domain(org, domain.id)


def test_bulk_headcounts_of_a_flat_org_are_empty():
    org = OrgState(teams=(Team("a", "A", True, 0.0),), workload=1)
    assert headcounts_by_domain(org) == {}
