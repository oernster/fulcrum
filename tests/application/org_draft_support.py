"""Shared builders for the org-draft test modules.

Not a test module: the three org-draft test files (structure, serialisation,
conversions) build their drafts and the reference blueprint from here so the
fixture exists once.
"""

from random import Random

from fulcrum.application.dto import (
    DependencySpec,
    DomainSpec,
    OrgBlueprint,
    TeamSpec,
)
from fulcrum.application.name_pool import NamePicker
from fulcrum.application.org_draft import OrgDraft


def make_draft() -> OrgDraft:
    return OrgDraft(NamePicker(Random(0)))


def make_blueprint() -> OrgBlueprint:
    return OrgBlueprint(
        teams=(
            TeamSpec(
                "team_1",
                "Checkout",
                True,
                0.25,
                domain_id="d2",
                size=2,
                owner="Priya Sharma",
                headcount=6,
            ),
            TeamSpec("team_2", "Free Agent", False, 0.4, headcount=4),
        ),
        dependencies=(DependencySpec("team_1", "team_2", 3),),
        workload=5,
        domains=(
            DomainSpec("d1", "Acme", lead="Kwame Mensah", category="Company"),
            DomainSpec(
                "d2",
                "Payments",
                parent_id="d1",
                category="Division",
                headcount=40,
            ),
        ),
    )


def make_imported_draft() -> OrgDraft:
    return OrgDraft.from_blueprint(make_blueprint(), NamePicker(Random(0)))
