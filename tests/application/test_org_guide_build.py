"""Tests for the guide's build pass: progress reporting and the growth line.

Split from test_org_guide so each file stays within the structural line
limit: this file covers how build_org_guide reports its work (sections,
guard pricing, growth valuations) and how the whole-org growth row is
planned; the guide's tree shape stays in test_org_guide.
"""

import pytest

from fulcrum.application.game_session import MAX_PLAYABLE_TEAMS
from fulcrum.application.org_guide import (
    GROWTH_FRAME_LABEL,
    LOOSE_TEAMS_LABEL,
    _Builder,
    build_org_guide,
)
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.hierarchy import TOP_LEVEL_FOCUS
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import MoveKind

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
        teams=(
            _t("a1", domain_id="d1"),
            _t("a2", domain_id="d1"),
            _t("b1", domain_id="d2a"),
            _t("b2", domain_id="d2b"),
        ),
        dependencies=(
            Dependency("a1", "a2", 4),
            Dependency("d1", "d2", 6),
        ),
        workload=2,
        domains=(
            Domain("d1", "Platform"),
            Domain("d2", "Product"),
            Domain("d2a", "Web", parent_id="d2"),
            Domain("d2b", "Mobile", parent_id="d2"),
            Domain("empty", "Empty"),
        ),
    )


def _mixed_org():
    """A mixed unit (a direct team beside a teamful child unit) plus a loose team."""
    return OrgState(
        teams=(
            _t("direct", domain_id="mix"),
            _t("s1", domain_id="sub"),
            _t("s2", authority=True, skew=0.0, domain_id="sub"),
            _t("loose"),
        ),
        dependencies=(Dependency("s1", "s2", 4),),
        workload=2,
        domains=(Domain("mix", "Mixed"), Domain("sub", "Sub", parent_id="mix")),
    )


def test_progress_reports_every_phase_and_ends_complete():
    seen = []
    build_org_guide(
        _hierarchical_org(),
        _SIM,
        progress=lambda done, total: seen.append((done, total)),
    )
    # Work units cover sections AND the guard's line pricing, so the bar
    # moves for the whole build: done is monotone, every report stays
    # within its declared total and the final snap closes the bar.
    dones = [done for done, _ in seen]
    assert dones == sorted(dones)
    assert all(done <= total for done, total in seen)
    assert seen[0][1] >= 4  # Platform, Product, Web, Mobile at least.
    assert seen[-1][0] == seen[-1][1]
    # Sections tick first; the guard extends the total once lines exist.
    assert seen[-1][1] > 4


def test_growth_flag_is_carried_on_the_result():
    fixed = build_org_guide(_hierarchical_org(), _SIM)
    grown = build_org_guide(_hierarchical_org(), _SIM, allow_growth=True)
    assert fixed.grown is False
    assert grown.grown is True


def _hub_org():
    """Single-team units around a loose hub whose coupling is all
    cross-boundary, the shape where only the whole org can price a split."""
    return OrgState(
        teams=(
            _t("a", authority=True, skew=0.2, domain_id="da"),
            _t("b", authority=True, skew=0.2, domain_id="db"),
            _t("c", skew=0.6, domain_id="dc"),
            _t("hub", skew=0.6),
        ),
        dependencies=(
            Dependency("a", "hub", 2),
            Dependency("b", "hub", 2),
            Dependency("c", "hub", 1),
            Dependency("a", "c", 2),
        ),
        workload=6,
        domains=(Domain("da", "A"), Domain("db", "B"), Domain("dc", "C")),
    )


def test_grown_guide_appends_a_whole_org_growth_row():
    fixed = build_org_guide(_hub_org(), _SIM)
    grown = build_org_guide(_hub_org(), _SIM, allow_growth=True)
    assert all(node.label != GROWTH_FRAME_LABEL for node in fixed.nodes)
    growth = grown.nodes[-1]
    assert growth.label == GROWTH_FRAME_LABEL
    assert growth.grown_line and growth.is_leaf and growth.playable
    assert growth.frame_id is None
    kinds = {step.move.kind for step in growth.guide.steps}
    assert kinds and kinds <= {MoveKind.SPLIT_TEAM, MoveKind.ADD_TEAM}
    # The leaf repairs are identical, so growth's org points are exactly
    # the headline improvement over the fixed-size guide.
    assert grown.flat_after > fixed.flat_after
    assert growth.org_delta == pytest.approx(grown.flat_after - fixed.flat_after)
    assert growth.org_delta == pytest.approx(
        growth.guide.final_score - growth.guide.start_score
    )


def test_the_top_frame_gets_no_row_even_when_growing():
    # No authority sits above the top level to make a move there, so no
    # top-frame row is planned in either mode; a loose team's own repairs
    # live in the loose-teams leaf row instead.
    org = OrgState(
        teams=(
            _t("a", authority=True, skew=0.2, domain_id="da"),
            _t("b", authority=True, skew=0.2, domain_id="db"),
            _t("hub", skew=0.6),
        ),
        dependencies=(
            Dependency("da", "hub", 2),
            Dependency("db", "hub", 2),
            Dependency("da", "db", 1),
        ),
        workload=6,
        domains=(Domain("da", "A"), Domain("db", "B")),
    )
    fixed = build_org_guide(org, _SIM)
    grown = build_org_guide(org, _SIM, allow_growth=True)
    for guide in (fixed, grown):
        assert all(node.frame_id != TOP_LEVEL_FOCUS for node in guide.nodes)
        loose = next(n for n in guide.nodes if n.label == LOOSE_TEAMS_LABEL)
        targets = {t for s in loose.guide.steps for t in s.move.targets}
        assert targets <= {"hub"}


def test_an_aggregate_unit_frame_keeps_growth_to_real_teams_when_growing():
    # A mixed unit's frame holds a coupled direct team beside coupled rolled
    # nodes; with growth on, the planner sees growth candidates for both and
    # must keep only the real team's (a rolled node cannot grow as one act).
    org = OrgState(
        teams=(
            _t("direct", skew=0.6, domain_id="mix"),
            _t("s1a", domain_id="s1"),
            _t("s2a", domain_id="s2"),
        ),
        dependencies=(
            Dependency("s1", "direct", 2),
            Dependency("s2", "direct", 2),
            Dependency("s1", "s2", 2),
        ),
        workload=6,
        domains=(
            Domain("mix", "Mixed"),
            Domain("s1", "SubOne", parent_id="mix"),
            Domain("s2", "SubTwo", parent_id="mix"),
        ),
    )
    grown = build_org_guide(org, _SIM, allow_growth=True)
    mixed = next(n for n in grown.nodes if n.label == "Mixed")
    growth_kinds = {MoveKind.SPLIT_TEAM, MoveKind.ADD_TEAM}
    for step in mixed.guide.steps:
        if step.move.kind in growth_kinds:
            assert all(org.has_team(target) for target in step.move.targets)


def test_growth_row_is_absent_when_growth_gains_nothing():
    org = OrgState(
        teams=(_t("a", domain_id="d1"), _t("b", domain_id="d2")),
        workload=2,
        domains=(Domain("d1", "One"), Domain("d2", "Two")),
    )
    fixed = build_org_guide(org, _SIM)
    grown = build_org_guide(org, _SIM, allow_growth=True)
    assert [n.label for n in grown.nodes] == [n.label for n in fixed.nodes]
    assert grown.flat_after == pytest.approx(fixed.flat_after)


def test_oversized_org_plans_growth_over_a_shortlist():
    """Past the live size growth is planned, never refused outright.

    The line considers only the most coupled teams, so no unplayable
    refusal row ever appears; when no shortlisted move clears the
    planner's bar the row is simply absent, like any other gainless line.
    """
    teams = tuple(_t(f"t{i}", domain_id="big") for i in range(MAX_PLAYABLE_TEAMS + 1))
    org = OrgState(
        teams=teams,
        workload=1,
        dependencies=(Dependency("t0", "t1", 2), Dependency("t2", "t0", 2)),
        domains=(Domain("big", "Big"),),
    )
    grown = build_org_guide(org, _SIM, allow_growth=True)
    assert all(not (n.grown_line and not n.playable) for n in grown.nodes)


def test_progress_counts_the_growth_pass_when_growing():
    seen = []
    build_org_guide(
        _hierarchical_org(),
        _SIM,
        allow_growth=True,
        progress=lambda done, total: seen.append((done, total)),
    )
    # Four sections plus the whole-org growth pass, whose candidate
    # valuations extend the total so the bar lives through the planning.
    assert seen[0] == (1, 5)
    dones = [done for done, _ in seen]
    assert dones == sorted(dones)
    assert all(done <= total for done, total in seen)
    assert seen[-1][0] == seen[-1][1]


def test_progress_counts_direct_and_loose_rows():
    seen = []
    build_org_guide(
        _mixed_org(), _SIM, progress=lambda done, total: seen.append((done, total))
    )
    # Loose row, Mixed, its direct row, Sub: four sections tick first,
    # then the guard's line pricing carries the bar to a closed total.
    assert seen[0] == (1, 4)
    assert seen[3][0] == 4
    assert seen[-1][0] == seen[-1][1]


def test_progress_total_follows_an_overrunning_phase():
    # An open-ended phase (an extra guard pass, growth past its estimate)
    # can tick beyond the declared total; the total follows so the bar
    # keeps moving instead of pinning full.
    seen = []
    builder = _Builder(
        _flat_org(), _SIM, False, lambda done, total: seen.append((done, total))
    )
    builder._extend(1)
    builder._tick()
    builder._tick()
    assert seen[-1] == (2, 2)
