"""Compile a plain org blueprint into a validated domain OrgState.

The wizard and every importer produce an OrgBlueprint; this is the single place
that turns one into a domain object, so all three origins share one validation
path.
"""

from __future__ import annotations

from fulcrum.application.dto import OrgBlueprint
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
        )
        for spec in blueprint.teams
    )
    dependencies = tuple(
        Dependency(spec.upstream, spec.downstream, spec.propagation_delay)
        for spec in blueprint.dependencies
    )
    domains = tuple(
        Domain(spec.id, spec.name, spec.parent_id, spec.lead)
        for spec in blueprint.domains
    )
    return OrgState(
        teams=teams,
        dependencies=dependencies,
        workload=blueprint.workload,
        origin=origin,
        domains=domains,
    )
