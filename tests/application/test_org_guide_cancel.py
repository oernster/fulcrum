"""Tests for cancelling a guide build mid-flight.

Cancellation is cooperative: a cancelled check rides into the planner
and the builder, is consulted at every step, valuation chunk and
progress tick, and a true answer abandons the build by raising
GuideBuildCancelled. A check that never fires must leave the build
byte-identical to one never asked.
"""

import pytest

from fulcrum.application.org_guide import build_org_guide
from fulcrum.application.org_guide_parallel import build_org_guide_auto
from fulcrum.application.planner import (
    GuideBuildCancelled,
    ImprovementPlanner,
    ensure_live,
)
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Dependency, Domain, OrgState, Team

_SIM = DeterministicSimulator()


def _t(team_id, authority=False, skew=0.4, domain_id=None):
    return Team(
        id=team_id,
        name=team_id.upper(),
        has_local_authority=authority,
        incentive_skew=skew,
        domain_id=domain_id,
    )


def _flat_org():
    return OrgState(
        teams=(_t("a"), _t("b", authority=True, skew=0.0)),
        dependencies=(Dependency("a", "b", 4),),
        workload=2,
    )


def _hierarchical_org():
    return OrgState(
        teams=(_t("a1", domain_id="d1"), _t("b1", domain_id="d2")),
        dependencies=(Dependency("a1", "b1", 4),),
        workload=2,
        domains=(Domain("d1", "Platform"), Domain("d2", "Product")),
    )


def test_ensure_live_raises_only_on_a_true_check():
    ensure_live(None)
    ensure_live(lambda: False)
    with pytest.raises(GuideBuildCancelled):
        ensure_live(lambda: True)


def test_a_never_cancelled_plan_matches_a_plain_plan():
    org = _flat_org()
    planned = ImprovementPlanner(_SIM).plan(org, cancelled=lambda: False)
    assert planned == ImprovementPlanner(_SIM).plan(org)


def test_a_cancelled_plan_stops_mid_flight():
    checks = []

    def cancelled():
        checks.append(1)
        return len(checks) > 1

    with pytest.raises(GuideBuildCancelled):
        ImprovementPlanner(_SIM).plan(_flat_org(), cancelled=cancelled)


def test_a_cancelled_build_raises_and_never_reports_complete():
    seen = []
    with pytest.raises(GuideBuildCancelled):
        build_org_guide(
            _hierarchical_org(),
            _SIM,
            progress=lambda done, total: seen.append((done, total)),
            cancelled=lambda: len(seen) >= 2,
        )
    assert seen
    assert all(done < total for done, total in seen)


def test_a_never_cancelled_build_matches_a_plain_build():
    org = _hierarchical_org()
    built = build_org_guide(org, _SIM, cancelled=lambda: False)
    assert built == build_org_guide(org, _SIM)


def test_the_auto_entry_forwards_cancellation():
    with pytest.raises(GuideBuildCancelled):
        build_org_guide_auto(_flat_org(), _SIM, cancelled=lambda: True)
