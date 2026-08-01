"""Process-parallel pricing for the guide build's independent workloads.

The guide's long phases are embarrassingly parallel and pure CPU: the
composition guard prices each leaf line independently (replaying every
other line against the whole organisation) and a growth step valuates
independent candidate moves. Threads cannot help (the interpreter lock
serialises pure-Python compute), so the pool runs worker processes.

Every task prices exactly what the serial loop prices and results are
reassembled in submission order, so the outcome is bit-identical to the
serial path; only the wall-clock differs. The pool is optional at every
call site: with no pool the serial loops run unchanged, which is also
the deterministic path small organisations and most tests take. A pool
that breaks mid-build (a worker killed externally) degrades to the same
serial pricing in-process rather than failing the build.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from typing import Self

from fulcrum.application.dto import MoveValuation
from fulcrum.application.game_session import MAX_PLAYABLE_TEAMS
from fulcrum.application.interfaces import Simulator
from fulcrum.application.org_guide import ProgressCallback, build_org_guide
from fulcrum.application.org_guide_model import OrgGuide
from fulcrum.domain.errors import FulcrumError
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, apply_move

# Task sizing: chunks a few items wide keep every worker busy to the end
# of a pass and tick progress steadily, while the shared payload (the
# org and the lines) is pickled once per task rather than once per item.
_LINES_PER_TASK = 3
_MOVES_PER_TASK = 16

# One core stays with the UI process so the event loop keeps painting.
_UI_RESERVED_CORES = 1
# Below this many workers the pool's spawn cost outweighs its parallelism.
_MIN_WORKERS = 2


def _replay_without(
    org: OrgState, line_moves: tuple[tuple[Move, ...], ...], skip: int
) -> OrgState:
    """Every line's moves but one applied, mirroring the guard's replay:
    a move that cannot apply stops its own line and the rest continue."""
    current = org
    for index, moves in enumerate(line_moves):
        if index == skip:
            continue
        for move in moves:
            try:
                current = apply_move(current, move)
            except FulcrumError:
                break
    return current


def _price_chunk(
    simulator: Simulator,
    org: OrgState,
    full: float,
    line_moves: tuple[tuple[Move, ...], ...],
    start: int,
    stop: int,
) -> tuple[float, ...]:
    """The guard's marginal price for each line in [start, stop)."""
    return tuple(
        full - simulator.score(_replay_without(org, line_moves, index)).value
        for index in range(start, stop)
    )


def _valuate_chunk(
    simulator: Simulator, org: OrgState, moves: tuple[Move, ...]
) -> tuple[MoveValuation, ...]:
    """One planner valuation chunk, exactly as the serial path prices it."""
    return simulator.valuate_moves(org, moves)


def _spans(count: int, size: int) -> tuple[tuple[int, int], ...]:
    return tuple((start, min(start + size, count)) for start in range(0, count, size))


class GuideWorkers:
    """A process pool implementing the GuideWorkerPool seam.

    Owns a ProcessPoolExecutor; use as a context manager so the workers
    are released when the build finishes.
    """

    def __init__(self, max_workers: int) -> None:
        self._pool = ProcessPoolExecutor(max_workers=max_workers)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._pool.shutdown()

    def price_lines(
        self,
        simulator: Simulator,
        org: OrgState,
        full: float,
        line_moves: tuple[tuple[Move, ...], ...],
        progress: Callable[[], None] | None,
    ) -> tuple[float, ...]:
        spans = _spans(len(line_moves), _LINES_PER_TASK)
        try:
            chunks = self._gather(
                {
                    self._pool.submit(
                        _price_chunk, simulator, org, full, line_moves, start, stop
                    ): position
                    for position, (start, stop) in enumerate(spans)
                },
                None if progress is None else lambda chunk: _each(progress, chunk),
            )
        except BrokenProcessPool:
            # Degrade in-process; a tick may repeat for a line the pool
            # already reported, which the bar's monotone clamp absorbs.
            chunks = []
            for start, stop in spans:
                chunks.append(
                    _price_chunk(simulator, org, full, line_moves, start, stop)
                )
                if progress is not None:
                    _each(progress, chunks[-1])
        return tuple(value for chunk in chunks for value in chunk)

    def valuate_moves(
        self,
        simulator: Simulator,
        org: OrgState,
        moves: tuple[Move, ...],
        progress: Callable[[int], None] | None,
    ) -> tuple[MoveValuation, ...]:
        spans = _spans(len(moves), _MOVES_PER_TASK)
        try:
            chunks = self._gather(
                {
                    self._pool.submit(
                        _valuate_chunk, simulator, org, moves[start:stop]
                    ): position
                    for position, (start, stop) in enumerate(spans)
                },
                None if progress is None else lambda chunk: progress(len(chunk)),
            )
        except BrokenProcessPool:
            chunks = [_valuate_chunk(simulator, org, moves)]
            if progress is not None:
                progress(len(moves))
        return tuple(valuation for chunk in chunks for valuation in chunk)

    def _gather(self, futures, report):
        """Chunk results in submission order, whatever order they finish."""
        chunks = [()] * len(futures)
        for future in as_completed(futures):
            chunk = future.result()
            chunks[futures[future]] = chunk
            if report is not None:
                report(chunk)
        return chunks


def _each(progress: Callable[[], None], chunk: tuple) -> None:
    for _ in chunk:
        progress()


def guide_workers_for(
    org: OrgState, cpu_count: int | None = None
) -> GuideWorkers | None:
    """A worker pool when the organisation is large enough to pay for one.

    A small organisation builds its guide in well under the pool's spawn
    time, so the live-planning size boundary marks where the machinery
    engages. cpu_count is injectable so tests stay machine-independent.
    """
    if len(org.teams) <= MAX_PLAYABLE_TEAMS:
        return None
    if cpu_count is None:
        cpu_count = os.process_cpu_count() or _MIN_WORKERS
    available = cpu_count - _UI_RESERVED_CORES
    if available < _MIN_WORKERS:
        return None
    return GuideWorkers(available)


def build_org_guide_auto(
    org: OrgState,
    simulator: Simulator,
    allow_growth: bool = False,
    progress: ProgressCallback | None = None,
    cpu_count: int | None = None,
) -> OrgGuide:
    """build_org_guide behind an automatically sized worker pool.

    The guide is identical with and without the pool; only the wall-clock
    differs. Callers that already hold a pool pass it to build_org_guide
    directly instead.
    """
    workers = guide_workers_for(org, cpu_count)
    if workers is None:
        return build_org_guide(org, simulator, allow_growth, progress)
    with workers:
        return build_org_guide(org, simulator, allow_growth, progress, workers)
