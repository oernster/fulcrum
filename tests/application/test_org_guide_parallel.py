"""Tests for the guide's worker pool: identical results, serial fallback.

The pool's contract is that a build with workers is bit-identical to the
serial build; these tests hold it to that on the worker functions (run
in-process so coverage sees them), on a live two-worker pool and on the
automatic entry the UI uses. Pool breakage degrades to serial pricing.
"""

import os
from concurrent.futures.process import BrokenProcessPool

import pytest

from fulcrum.application.game_session import MAX_PLAYABLE_TEAMS
from fulcrum.application.org_guide import build_org_guide
from fulcrum.application.org_guide_parallel import (
    GuideWorkers,
    _price_chunk,
    _replay_without,
    _valuate_chunk,
    build_org_guide_auto,
    guide_workers_for,
)
from fulcrum.application.planner import ImprovementPlanner
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind

_SIM = DeterministicSimulator()


def _t(team_id, authority=False, skew=0.4, domain_id=None):
    return Team(
        id=team_id,
        name=team_id.upper(),
        has_local_authority=authority,
        incentive_skew=skew,
        domain_id=domain_id,
    )


def _small_org():
    return OrgState(
        teams=(_t("a"), _t("b", authority=True, skew=0.0)),
        dependencies=(Dependency("a", "b", 4),),
        workload=2,
    )


def _big_org():
    """Two plannable halves just past the live-planning size, so the
    factory engages and the guard has real lines to price."""
    half = MAX_PLAYABLE_TEAMS // 2 + 1
    teams = tuple(_t(f"p{i}", domain_id="d1") for i in range(half)) + tuple(
        _t(f"q{i}", domain_id="d2") for i in range(half)
    )
    return OrgState(
        teams=teams,
        dependencies=(Dependency("p0", "p1", 4), Dependency("q0", "q1", 4)),
        workload=2,
        domains=(Domain("d1", "One"), Domain("d2", "Two")),
    )


def _line_moves():
    return (
        (Move(MoveKind.DELEGATE_AUTHORITY, ("a",)),),
        (Move(MoveKind.REALIGN_INCENTIVES, ("a",)),),
    )


def test_worker_functions_match_the_serial_primitives():
    org = _small_org()
    lines = _line_moves()
    # Skipping a line replays only the other one.
    replayed = _replay_without(org, lines, 1)
    assert replayed.team("a").has_local_authority
    assert replayed.team("a").incentive_skew == org.team("a").incentive_skew
    # A line whose move cannot apply stops that line and the rest apply.
    broken = ((Move(MoveKind.DELEGATE_AUTHORITY, ("ghost",)),),) + lines
    assert _replay_without(org, broken, -1) == _replay_without(org, lines, -1)
    full = _SIM.score(_replay_without(org, lines, -1)).value
    priced = _price_chunk(_SIM, org, full, lines, 0, len(lines))
    expected = tuple(
        full - _SIM.score(_replay_without(org, lines, index)).value
        for index in range(len(lines))
    )
    assert priced == expected
    moves = tuple(line[0] for line in lines)
    assert _valuate_chunk(_SIM, org, moves) == _SIM.valuate_moves(org, moves)


def test_pool_prices_and_valuates_identically_to_serial():
    org = _small_org()
    lines = _line_moves()
    full = _SIM.score(_replay_without(org, lines, -1)).value
    moves = tuple(line[0] for line in lines)
    ticks = []
    counts = []
    with GuideWorkers(2) as workers:
        priced = workers.price_lines(_SIM, org, full, lines, lambda: ticks.append(1))
        valuations = workers.valuate_moves(
            _SIM, org, moves, lambda count: counts.append(count)
        )
    assert priced == _price_chunk(_SIM, org, full, lines, 0, len(lines))
    assert valuations == _SIM.valuate_moves(org, moves)
    assert len(ticks) == len(lines)
    assert sum(counts) == len(moves)


def test_a_broken_pool_degrades_to_serial_pricing():
    org = _small_org()
    lines = _line_moves()
    full = _SIM.score(_replay_without(org, lines, -1)).value
    moves = tuple(line[0] for line in lines)
    ticks = []
    counts = []
    with GuideWorkers(2) as workers:
        with pytest.raises(BrokenProcessPool):
            workers._pool.submit(os._exit, 1).result()
        priced = workers.price_lines(_SIM, org, full, lines, lambda: ticks.append(1))
        valuations = workers.valuate_moves(
            _SIM, org, moves, lambda count: counts.append(count)
        )
    assert priced == _price_chunk(_SIM, org, full, lines, 0, len(lines))
    assert valuations == _SIM.valuate_moves(org, moves)
    assert len(ticks) == len(lines)
    assert sum(counts) == len(moves)


def test_factory_gates_on_organisation_size_and_cores():
    assert guide_workers_for(_small_org(), cpu_count=24) is None
    big = _big_org()
    # Too few cores to leave the UI one and still parallelise.
    assert guide_workers_for(big, cpu_count=2) is None
    pool = guide_workers_for(big, cpu_count=3)
    assert pool is not None
    with pool:
        pass
    # The machine's own count is consulted only when none is injected.
    detected = guide_workers_for(big)
    if detected is not None:
        with detected:
            pass


class _RecordingPool:
    """Hand-written fake of the GuideWorkerPool seam, serial and in-process."""

    def __init__(self):
        self.valuations = 0

    def valuate_moves(self, simulator, org, moves, progress, cancelled=None):
        self.valuations += 1
        result = simulator.valuate_moves(org, moves)
        if progress is not None:
            progress(len(moves))
        return result


def test_planner_delegates_valuation_to_the_pool():
    org = _small_org()
    pool = _RecordingPool()
    counts = []
    pooled = ImprovementPlanner(_SIM).plan(org, progress=counts.append, workers=pool)
    assert pool.valuations > 0
    assert sum(counts) > 0
    assert pooled == ImprovementPlanner(_SIM).plan(org)


def test_auto_build_matches_the_serial_build():
    small = _small_org()
    assert build_org_guide_auto(small, _SIM) == build_org_guide(small, _SIM)
    big = _big_org()
    serial = build_org_guide(big, _SIM)
    pooled = build_org_guide_auto(big, _SIM, cpu_count=3)
    assert pooled == serial
