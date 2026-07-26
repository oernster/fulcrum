"""Tests for authority claims in the shared JSON serialization."""

from fulcrum.domain.models import AuthorityClaim, OrgState, Team
from fulcrum.infrastructure.json_serialization import org_from_dict, org_to_dict


def _org():
    return OrgState(
        teams=(Team("a", "A", True), Team("b", "B", False)),
        workload=2,
        claims=(
            AuthorityClaim("b", "a"),
            AuthorityClaim("Head of QA", "a"),
        ),
    )


def test_claims_round_trip_through_the_dict_shape():
    data = org_to_dict(_org())
    assert data["claims"] == [
        {"claimant": "b", "subject": "a"},
        {"claimant": "Head of QA", "subject": "a"},
    ]
    assert org_from_dict(data) == _org()


def test_a_legacy_dict_without_claims_reads_as_unclaimed():
    data = org_to_dict(_org())
    del data["claims"]
    assert org_from_dict(data).claims == ()
