"""Default plan exporter: writes the HTML report and the JSON source together.

Given a chosen .html path, it writes the self-contained report there and a
re-importable .json beside it, so the same export both elucidates the plan and
can be loaded back to edit it.
"""

from __future__ import annotations

from pathlib import Path

from fulcrum.application.dto import Plan, PlanReport
from fulcrum.domain.models import OrgState
from fulcrum.infrastructure.plan_html import render_plan_html
from fulcrum.infrastructure.plan_repository import read_plan, write_html, write_plan

_JSON_SUFFIX = ".json"


class FilePlanExporter:
    """Writes the plan's HTML report and its JSON source side by side."""

    def export(
        self,
        html_path: str,
        report: PlanReport,
        plan: Plan,
        final_org: OrgState,
        created_at: str,
    ) -> None:
        target = Path(html_path)
        html = render_plan_html(report, plan.initial_org, final_org, created_at)
        write_html(target, html)
        write_plan(target.with_suffix(_JSON_SUFFIX), plan)

    def read(self, path: str) -> Plan:
        return read_plan(Path(path))
