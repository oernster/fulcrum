"""Blueprint serialisation for the org draft, as a capability mixin.

OrgDraft mixes this in; splitting it out keeps each module within the
structural line limit. A draft converts losslessly to and from an
OrgBlueprint, which is both how a fresh model leaves the editor and how an
existing org re-enters it.
"""

from __future__ import annotations

from fulcrum.application.dto import DomainSpec, OrgBlueprint, TeamSpec
from fulcrum.application.name_pool import NamePicker
from fulcrum.application.org_draft_nodes import ContainerDraft, TeamDraft

_PERCENT = 100


class DraftSerialisation:
    """from_blueprint and to_blueprint, mixed into OrgDraft."""

    @classmethod
    def from_blueprint(cls, blueprint: OrgBlueprint, names: NamePicker):
        """Rebuild an editable draft from a blueprint, filling blank names."""
        draft = cls(names, workload=blueprint.workload)
        containers: dict[str, ContainerDraft] = {}
        for spec in blueprint.domains:
            containers[spec.id] = ContainerDraft(
                id=spec.id,
                category=spec.category,
                name=spec.name,
                lead=spec.lead or names.draw(),
                unit_headcount=spec.headcount,
            )
        for spec in blueprint.domains:
            parent = containers.get(spec.parent_id) if spec.parent_id else None
            siblings = parent.children if parent is not None else draft.roots
            siblings.append(containers[spec.id])
        for team_spec in blueprint.teams:
            team = TeamDraft(
                id=team_spec.id,
                name=team_spec.name,
                people=team_spec.headcount,
                ships_without_asking=team_spec.has_local_authority,
                skew_percent=round(team_spec.incentive_skew * _PERCENT),
                owner=team_spec.owner or names.draw(),
                size=team_spec.size,
            )
            parent = (
                containers.get(team_spec.domain_id) if team_spec.domain_id else None
            )
            siblings = parent.children if parent is not None else draft.roots
            siblings.append(team)
        draft.dependencies = blueprint.dependencies
        draft._container_count = len(blueprint.domains)
        draft._team_count = len(blueprint.teams)
        return draft

    def to_blueprint(self) -> OrgBlueprint:
        """Serialise the draft back to the shared blueprint shape."""
        domains: list[DomainSpec] = []
        teams: list[TeamSpec] = []

        def visit(node, parent_id: str | None) -> None:
            if isinstance(node, ContainerDraft):
                domains.append(
                    DomainSpec(
                        id=node.id,
                        name=node.name or node.id,
                        parent_id=parent_id,
                        lead=node.lead,
                        category=node.category,
                        headcount=node.unit_headcount,
                    )
                )
                for child in node.children:
                    visit(child, node.id)
            else:
                teams.append(
                    TeamSpec(
                        id=node.id,
                        name=node.name or node.id,
                        has_local_authority=node.ships_without_asking,
                        incentive_skew=node.skew_percent / _PERCENT,
                        domain_id=parent_id,
                        size=node.size,
                        owner=node.owner,
                        headcount=node.people,
                    )
                )

        for root in self.roots:
            visit(root, None)
        team_ids = {team.id for team in teams}
        dependencies = tuple(
            dep
            for dep in self.dependencies
            if dep.upstream in team_ids and dep.downstream in team_ids
        )
        return OrgBlueprint(
            teams=tuple(teams),
            dependencies=dependencies,
            workload=self.workload,
            domains=tuple(domains),
        )
