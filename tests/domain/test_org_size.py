"""Tests for the organisation size bands."""

import pytest

from fulcrum.domain.errors import InvalidOrgStateError
from fulcrum.domain.org_size import DEFAULT_BAND, ORG_SIZE_BANDS, OrgSizeBand


def _band(**overrides):
    base = {
        "key": "k",
        "label": "L",
        "descriptor": "D",
        "min_people": 5,
        "max_people": 10,
    }
    base.update(overrides)
    return OrgSizeBand(**base)


def test_band_exposes_midpoint_and_membership():
    band = _band(min_people=10, max_people=20)
    assert band.midpoint == 15
    assert band.contains(10)
    assert band.contains(20)
    assert not band.contains(9)
    assert not band.contains(21)


@pytest.mark.parametrize(
    "overrides",
    [
        {"key": ""},
        {"label": ""},
        {"descriptor": ""},
        {"min_people": 0, "max_people": 5},
        {"min_people": 10, "max_people": 9},
    ],
)
def test_invalid_band_is_rejected(overrides):
    with pytest.raises(InvalidOrgStateError):
        _band(**overrides)


def test_bands_are_named_and_cover_a_growing_range():
    assert DEFAULT_BAND in ORG_SIZE_BANDS
    keys = [band.key for band in ORG_SIZE_BANDS]
    assert keys == ["tiny", "small", "medium", "large", "huge", "massive"]
    for earlier, later in zip(ORG_SIZE_BANDS, ORG_SIZE_BANDS[1:]):
        assert later.min_people >= earlier.min_people
        assert later.max_people > earlier.max_people
