"""Default plan exporter: writes the HTML report or the JSON source.

Each export is independent, so the user can save just the shareable HTML report
or just the re-importable JSON plan rather than always producing both.
"""

from __future__ import annotations

from pathlib import Path

from fulcrum.application.dto import Plan, PlanReport
from fulcrum.domain.models import OrgState
from fulcrum.infrastructure.plan_html import render_plan_html
from fulcrum.infrastructure.plan_repository import read_plan, write_html, write_plan


class FilePlanExporter:
    """Writes the plan's HTML report or its JSON source, each on its own."""

    def export_html(
        self,
        path: str,
        report: PlanReport,
        initial_org: OrgState,
        final_org: OrgState,
        created_at: str,
    ) -> None:
        html = render_plan_html(report, initial_org, final_org, created_at)
        write_html(Path(path), html)

    def export_json(self, path: str, plan: Plan) -> None:
        write_plan(Path(path), plan)

    def read(self, path: str) -> Plan:
        return read_plan(Path(path))
