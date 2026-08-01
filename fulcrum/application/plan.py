"""Turn a played plan into a scored, justified, per-domain report.

Replaying the moves from the starting org, each step is scored, classified and
attributed to the domain it acts on (or to the CTO when it spans domains or is
org-wide), with a plain rationale naming the signal it most eased. Steps are
then grouped into per-domain recommendations addressed to each domain's lead,
which is what the export hands to the C-suite and to senior leads.
"""

from __future__ import annotations

from fulcrum.application.dto import (
    DomainRecommendation,
    FrameAssessment,
    PlanReport,
    PlanStep,
)
from fulcrum.application.interfaces import Simulator
from fulcrum.application.move_text import describe_move
from fulcrum.domain.hierarchy import focused_suborg
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, apply_move
from fulcrum.domain.signals import compute_signals, format_reading_value
from fulcrum.domain.simulation import DEFAULT_THRESHOLDS, classify_delta
from fulcrum.shared.text import SCORE_DECIMALS

_ORG_WIDE_LABEL = "Organisation-wide (CTO)"
_NO_LEAD = ""
_EPS = 1e-6


def build_plan_report(
    initial_org: OrgState,
    moves: tuple[Move, ...],
    simulator: Simulator,
    prior_moves: int = 0,
) -> PlanReport:
    """Score and justify each move from the start org, grouped by domain.

    The first prior_moves entries are the record of earlier runs and their
    steps are marked historic, so the report can separate them visually
    from the current run's work.
    """
    start_score = simulator.score(initial_org).value
    current = initial_org
    before = start_score
    steps: list[PlanStep] = []
    for index, move in enumerate(moves):
        after_org = apply_move(current, move)
        after = simulator.score(after_org).value
        classification = classify_delta(after - before, DEFAULT_THRESHOLDS)
        description = describe_move(current, move)
        domain_id, label, lead = _attribute(current, move)
        rationale = _rationale(
            description,
            before,
            after,
            compute_signals(current),
            compute_signals(after_org),
            classification.value,
        )
        steps.append(
            PlanStep(
                description=description,
                classification=classification,
                score_before=before,
                score_after=after,
                domain_id=domain_id,
                domain_label=label,
                lead=lead,
                rationale=rationale,
                historic=index < prior_moves,
                local=_local_assessment(current, after_org, move, simulator),
            )
        )
        current = after_org
        before = after
    final_score = steps[-1].score_after if steps else start_score
    return PlanReport(
        start_score=start_score,
        final_score=final_score,
        steps=tuple(steps),
        recommendations=_group(steps),
    )


def _ancestry(org: OrgState, domain_id: str) -> tuple[str, ...]:
    """The domain's chain of ids from the root down to the domain itself."""
    by_id = {d.id: d for d in org.domains}
    chain: list[str] = []
    current: str | None = domain_id
    while current is not None:
        chain.append(current)
        current = by_id[current].parent_id
    return tuple(reversed(chain))


def _local_frame(org: OrgState, targets: tuple[str, ...]) -> str | None:
    """The deepest domain whose subtree holds every target, or None.

    A team target is located by its domain; a frame-node target (a scoped
    stabilise names the frame's child units) is located as that domain
    itself; an id the org cannot locate (an unmodelled claimant) contributes
    nothing. An empty target list, a loose team or targets with no shared
    unit all mean the move is org-wide and has no local frame.
    """
    known = {d.id for d in org.domains}
    chains: list[tuple[str, ...]] = []
    for target in targets:
        if org.has_team(target):
            domain_id = org.team(target).domain_id
        elif target in known:
            domain_id = target
        else:
            continue
        if domain_id is None:
            return None
        chains.append(_ancestry(org, domain_id))
    if not chains:
        return None
    deepest: str | None = None
    for level in zip(*chains):
        if len(set(level)) != 1:
            break
        deepest = level[0]
    return deepest


def _local_assessment(
    before_org: OrgState, after_org: OrgState, move: Move, simulator: Simulator
) -> FrameAssessment | None:
    """The move judged within its own frame, where one exists.

    The frame is scored exactly as the board scores it when the player
    drills in, so a move played as good inside a unit reads as good here
    even when its whole-org effect is far below the good threshold.
    """
    frame_id = _local_frame(before_org, move.targets)
    if frame_id is None:
        return None
    before = simulator.score(focused_suborg(before_org, frame_id)).value
    after = simulator.score(focused_suborg(after_org, frame_id)).value
    by_id = {d.id: d for d in before_org.domains}
    return FrameAssessment(
        frame_label=by_id[frame_id].name,
        classification=classify_delta(after - before, DEFAULT_THRESHOLDS),
        score_before=before,
        score_after=after,
    )


def _attribute(org: OrgState, move: Move) -> tuple[str | None, str, str]:
    domains = {
        org.team(team_id).domain_id for team_id in move.targets if org.has_team(team_id)
    }
    if len(domains) == 1:
        domain_id = next(iter(domains))
        if domain_id is not None:
            by_id = {d.id: d for d in org.domains}
            domain = by_id[domain_id]
            return domain_id, domain.name, domain.lead
    return None, _ORG_WIDE_LABEL, _NO_LEAD


def _best_easing(signals_before, signals_after):
    """The biggest easing the reader can actually see, or None.

    A signal only counts when its displayed value changes: a drop that
    rounds away at display precision must never be reported as a fall
    ("46% -> 46%" reads as a contradiction, not an easing).
    """
    best = None
    for reading_before, reading_after in zip(signals_before, signals_after):
        drop = reading_before.value - reading_after.value
        if drop <= _EPS:
            continue
        if format_reading_value(reading_before) == format_reading_value(reading_after):
            continue
        if best is None or drop > best[0].value - best[1].value:
            best = (reading_before, reading_after)
    return best


def _rationale(
    description: str,
    before: float,
    after: float,
    signals_before,
    signals_after,
    classification: str,
) -> str:
    best = _best_easing(signals_before, signals_after)
    health = (
        f"structural health {before:.{SCORE_DECIMALS}f} -> "
        f"{after:.{SCORE_DECIMALS}f} ({classification})"
    )
    if best is not None:
        eased_from, eased_to = best
        eased = (
            f"{eased_from.definition.label} falls "
            f"{format_reading_value(eased_from)} -> {format_reading_value(eased_to)}"
        )
        return f"{description}: {eased}; {health}."
    return f"{description}: {health}."


def _group(steps: list[PlanStep]) -> tuple[DomainRecommendation, ...]:
    order: list[str | None] = []
    grouped: dict[str | None, list[PlanStep]] = {}
    for step in steps:
        if step.domain_id not in grouped:
            grouped[step.domain_id] = []
            order.append(step.domain_id)
        grouped[step.domain_id].append(step)
    return tuple(
        DomainRecommendation(
            domain_id=key,
            label=grouped[key][0].domain_label,
            lead=grouped[key][0].lead,
            steps=tuple(grouped[key]),
        )
        for key in order
    )
