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
    parts.extend(_recommendation_html(rec) for rec in report.recommendations)
    parts.append("</div></body></html>")
    return "".join(parts)


def _summary_html(
    report: PlanReport, initial_org: OrgState, final_org: OrgState
) -> str:
    delta = report.final_score - report.start_score
    return "".join(
        [
            '<div class="card">',
            '<p class="score-line">Structural health: ',
            f"<b>{report.start_score:.1f}</b> &rarr; <b>{report.final_score:.1f}</b> ",
            f"({delta:+.1f}) over {len(report.steps)} moves.</p>",
            '<div class="maps">',
            f"<figure><figcaption>Before</figcaption>"
            f"{render_overview_svg(initial_org)}</figure>",
            f"<figure><figcaption>After</figcaption>"
            f"{render_overview_svg(final_org)}</figure>",
            "</div></div>",
        ]
    )


def _recommendation_html(rec: DomainRecommendation) -> str:
    if rec.domain_id is None:
        heading = "Organisation-wide moves (held by the CTO)"
    else:
        who = escape(rec.lead) if rec.lead else "the domain lead"
        heading = f"{escape(rec.label)} (for {who})"
    steps = "".join(_step_html(step) for step in rec.steps)
    return f'<section class="rec"><h3>{heading}</h3><ol>{steps}</ol></section>'


def _step_html(step: PlanStep) -> str:
    colour = _BADGE.get(step.classification.value, _BADGE_DEFAULT)
    return "".join(
        [
            "<li>",
            f'<span class="badge" style="background:{colour}">',
            f"{escape(step.classification.value)}</span> ",
            f"<b>{escape(step.description)}</b> ",
            f'<span class="score">{step.score_before:.1f} &rarr; '
            f"{step.score_after:.1f}</span>",
            f'<div class="rationale">{escape(step.rationale)}</div>',
            "</li>",
        ]
    )
