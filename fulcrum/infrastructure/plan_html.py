"""Render a plan report as a self-contained HTML document for distribution.

The document leads with a C-suite summary (the health change and before/after
org maps) and then a section per domain addressed to that domain's lead, each
listing the recommended moves with their classification and a plain rationale.
All styling is inline so the file stands alone; all user text is escaped.
"""

from __future__ import annotations

from html import escape

from fulcrum.application.dto import DomainRecommendation, PlanReport, PlanStep
from fulcrum.domain.models import OrgState
from fulcrum.infrastructure.svg_map import render_overview_svg
from fulcrum.shared.text import SCORE_DECIMALS, count_noun

_BADGE = {
    "great": "#34d399",
    "good": "#34d399",
    "neutral": "#9aa3af",
    "bad": "#f87171",
    "blunder": "#f87171",
}
_BADGE_DEFAULT = "#9aa3af"

_STYLE = (
    "body{background:#0d0f12;color:#e6e9ee;"
    "font-family:Segoe UI,Arial,sans-serif;margin:0}"
    ".wrap{max-width:900px;margin:0 auto;padding:32px}"
    "h1{color:#fbbf24}"
    "h2{color:#f59e0b;border-bottom:1px solid #2c333d;padding-bottom:6px}"
    ".muted{color:#9aa3af}"
    ".card,.rec{background:#1a1e24;border:1px solid #2c333d;"
    "border-radius:10px;padding:16px;margin:16px 0}"
    ".maps{display:flex;gap:24px;flex-wrap:wrap}"
    "figure{margin:0}figcaption{color:#9aa3af;margin-bottom:6px}"
    "ol{line-height:1.6}li{margin-bottom:12px}"
    ".badge{border-radius:4px;padding:2px 8px;color:#0d0f12;"
    "font-weight:600;font-size:12px}"
    ".score{color:#9aa3af;margin-left:8px}"
    ".rationale{color:#9aa3af;margin-top:4px}"
    ".score-line{font-size:18px}"
    # Earlier runs read as the record: muted text behind a grey rail; the
    # current run keeps full colour behind an amber rail.
    "li.historic{border-left:3px solid #2c333d;padding-left:10px}"
    "li.historic b,li.historic .badge{opacity:0.55}"
    "li.current{border-left:3px solid #f59e0b;padding-left:10px}"
    ".legend{color:#9aa3af}"
    ".legend .rail{display:inline-block;width:10px;height:10px;"
    "border-radius:2px;margin-right:6px}"
)

_LEGEND = (
    '<p class="legend">'
    '<span class="rail" style="background:#2c333d"></span>'
    "moves from earlier runs&nbsp;&nbsp;&nbsp;"
    '<span class="rail" style="background:#f59e0b"></span>'
    "moves from this run</p>"
)


def render_plan_html(
    report: PlanReport,
    initial_org: OrgState,
    final_org: OrgState,
    created_at: str,
) -> str:
    """Return a standalone HTML report for a completed plan."""
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>Fulcrum plan</title><style>{_STYLE}</style></head><body>",
        '<div class="wrap">',
        "<h1>Fulcrum: decision plan</h1>",
        f'<p class="muted">Generated {escape(created_at)}</p>',
        _summary_html(report, initial_org, final_org),
        "<h2>Recommendations by domain</h2>",
    ]
    # The rails only appear when there is a record to separate: a report
    # with no earlier runs keeps the plain single-history look.
    split = any(step.historic for step in report.steps)
    parts.extend(_recommendation_html(rec, split) for rec in report.recommendations)
    parts.append("</div></body></html>")
    return "".join(parts)


def _summary_html(
    report: PlanReport, initial_org: OrgState, final_org: OrgState
) -> str:
    delta = report.final_score - report.start_score
    historic = sum(1 for step in report.steps if step.historic)
    breakdown = ""
    if historic:
        current = len(report.steps) - historic
        breakdown = (
            f'<p class="muted">{count_noun(historic, "move")} from earlier '
            f'runs, {count_noun(current, "move")} this run.</p>{_LEGEND}'
        )
    return "".join(
        [
            '<div class="card">',
            '<p class="score-line">Structural health: ',
            (
                f"<b>{report.start_score:.{SCORE_DECIMALS}f}</b> &rarr; "
                f"<b>{report.final_score:.{SCORE_DECIMALS}f}</b> "
            ),
            (
                f"({delta:+.{SCORE_DECIMALS}f}) over "
                f"{count_noun(len(report.steps), 'move')}.</p>"
            ),
            breakdown,
            '<div class="maps">',
            (
                f"<figure><figcaption>Before</figcaption>"
                f"{render_overview_svg(initial_org)}</figure>"
            ),
            (
                f"<figure><figcaption>After</figcaption>"
                f"{render_overview_svg(final_org)}</figure>"
            ),
            "</div></div>",
        ]
    )


def _recommendation_html(rec: DomainRecommendation, split: bool) -> str:
    if rec.domain_id is None:
        heading = "Organisation-wide moves (held by the CTO)"
    else:
        who = escape(rec.lead) if rec.lead else "the domain lead"
        heading = f"{escape(rec.label)} (for {who})"
    steps = "".join(_step_html(step, split) for step in rec.steps)
    return f'<section class="rec"><h3>{heading}</h3><ol>{steps}</ol></section>'


def _step_html(step: PlanStep, split: bool) -> str:
    colour = _BADGE.get(step.classification.value, _BADGE_DEFAULT)
    css = ""
    if split:
        css = ' class="historic"' if step.historic else ' class="current"'
    return "".join(
        [
            f"<li{css}>",
            f'<span class="badge" style="background:{colour}">',
            f"{escape(step.classification.value)}</span> ",
            f"<b>{escape(step.description)}</b> ",
            (
                f'<span class="score">{step.score_before:.{SCORE_DECIMALS}f} &rarr; '
                f"{step.score_after:.{SCORE_DECIMALS}f}</span>"
            ),
            f'<div class="rationale">{escape(step.rationale)}</div>',
            "</li>",
        ]
    )
