"""Tests for the signal definitions and readings."""

import pytest

from fulcrum.domain.models import Dependency, OrgState, Team
from fulcrum.domain.signals import (
    ESCALATIONS,
    INFLUENCE,
    QUEUE_AGE,
    REWORK_RATE,
    SIGNAL_DEFINITIONS,
    compute_signals,
    definition,
)


def _t(team_id, authority=True, skew=0.0):
    return Team(
        id=team_id,
        name=team_id.upper(),
        has_local_authority=authority,
        incentive_skew=skew,
    )


def test_definition_lookup():
    assert definition(QUEUE_AGE).label == "Handoff queue age"
    assert len(SIGNAL_DEFINITIONS) == 4


def test_compute_signals_values_and_order():
    org = OrgState(
        teams=(_t("a", False, 0.4), _t("b", True, 0.6)),
        dependencies=(Dependency("a", "b", 4),),
        workload=6,
    )
    readings = compute_signals(org)
    keys = tuple(r.definition.key for r in readings)
    assert keys == (QUEUE_AGE, ESCALATIONS, REWORK_RATE, INFLUENCE)
    by_key = {r.definition.key: r.value for r in readings}
    assert by_key[ESCALATIONS] == 1.0
    assert by_key[REWORK_RATE] == pytest.approx((0.4 + 0.6) / 2 * 100)
    assert by_key[QUEUE_AGE] >= 0.0
    assert by_key[INFLUENCE] >= 0.0


def test_influence_signal_reads_the_load_for_an_authority_less_hub():
    org = OrgState(
        teams=(_t("hub", False), _t("a"), _t("b")),
        dependencies=(Dependency("hub", "a", 0), Dependency("hub", "b", 0)),
        workload=1,
    )
    by_key = {r.definition.key: r.value for r in compute_signals(org)}
    assert by_key[INFLUENCE] == 1.0
