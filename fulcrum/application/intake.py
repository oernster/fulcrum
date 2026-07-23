"""Compile a plain org blueprint into a validated domain OrgState and back.

The wizard and every importer produce an OrgBlueprint; this is the single place
that turns one into a domain object, so all three origins share one validation
path. The reverse direction serialises a live org back to a blueprint, which is
how "Edit my org" reopens any model (wizard-built, imported, generated or a
previous edit) in the editor with nothing lost.
"""

from __future__ import annotations

from fulcrum.application.dto import DependencySpec, DomainSpec, OrgBlueprint, TeamSpec
from fulcrum.domain.models import Dependency, Domain, Origin, OrgState, Team


def build_org_state(blueprint: OrgBlueprint, origin: Origin) -> OrgState:
    """Build a validated OrgState from a blueprint, tagging where it came from."""
    teams = tuple(
        Team(
            spec.id,
            spec.name,
            spec.has_local_authority,
            spec.incentive_skew,
            spec.domain_id,
            spec.size,
            spec.owner,
            spec.headcount,
        )
        for spec in blueprint.teams
    )
    dependencies = tuple(
        Dependency(spec.upstream, spec.downstream, spec.propagation_delay)
        for spec in blueprint.dependencies
    )
    domains = tuple(
        Domain(
            spec.id,
            spec.name,
            spec.parent_id,
            spec.lead,
            spec.category,
            spec.headcount,
        )
        for spec in blueprint.domains
    )
    return OrgState(
        teams=teams,
        dependencies=dependencies,
        workload=blueprint.workload,
        origin=origin,
        domains=domains,
    )


def org_to_blueprint(org: OrgState) -> OrgBlueprint:
    """Serialise a live org back to the blueprint shape the editor consumes."""
    teams = tuple(
        TeamSpec(
            id=team.id,
            name=team.name,
            has_local_authority=team.has_local_authority,
            incentive_skew=team.incentive_skew,
            domain_id=team.domain_id,
            size=team.size,
            owner=team.owner,
            headcount=team.headcount,
        )
        for team in org.teams
    )
    dependencies = tuple(
        DependencySpec(dep.upstream, dep.downstream, dep.propagation_delay)
        for dep in org.dependencies
    )
    domains = tuple(
        DomainSpec(
            id=domain.id,
            name=domain.name,
            parent_id=domain.parent_id,
            lead=domain.lead,
            category=domain.category,
            headcount=domain.headcount,
        )
        for domain in org.domains
    )
    return OrgBlueprint(
        teams=teams,
        dependencies=dependencies,
        workload=org.workload,
        domains=domains,
    )
