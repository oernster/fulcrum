"""Turn a played plan into a scored, justified, per-domain report.

Replaying the moves from the starting org, each step is scored, classified and
attributed to the domain it acts on (or to the CTO when it spans domains or is
org-wide), with a plain rationale naming the signal it most eased. Steps are
then grouped into per-domain recommendations addressed to each domain's lead,
which is what the export hands to the C-suite and to senior leads.
"""

from __future__ import annotations

from fulcrum.application.dto import DomainRecommendation, PlanReport, PlanStep
from fulcrum.application.interfaces import Simulator
from fulcrum.application.move_text import describe_move
from fulcrum.domain.models import OrgState
from fulcrum.domain.moves import Move, apply_move
from fulcrum.domain.signals import compute_signals, format_reading_value
from fulcrum.domain.simulation import DEFAULT_THRESHOLDS, classify_delta

_ORG_WIDE_LABEL = "Organisation-wide (CTO)"
_NO_LEAD = ""
_EPS = 1e-6


def build_plan_report(
    initial_org: OrgState, moves: tuple[Move, ...], simulator: Simulator
) -> PlanReport:
    """Score and justify each move from the start org, grouped by domain."""
    start_score = simulator.score(initial_org).value
    current = initial_org
    steps: list[PlanStep] = []
    for move in moves:
        before = simulator.score(current).value
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
            )
        )
        current = after_org
    final_score = steps[-1].score_after if steps else start_score
    return PlanReport(
        start_score=start_score,
        final_score=final_score,
        steps=tuple(steps),
        recommendations=_group(steps),
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


def _rationale(
    description: str,
    before: float,
    after: float,
    signals_before,
    signals_after,
    classification: str,
) -> str:
    best = None
    for reading_before, reading_after in zip(signals_before, signals_after):
        drop = reading_before.value - reading_after.value
        if best is None or drop > best[0].value - best[1].value:
            best = (reading_before, reading_after)
    eased_from, eased_to = best
    health = f"structural health {before:.1f} -> {after:.1f} ({classification})"
    if eased_from.value - eased_to.value > _EPS:
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
