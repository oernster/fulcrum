"""Scale-dependent authority pricing: the prince band.

Machiavelli holds both positions and scale reconciles them. In The Prince,
concentrated authority governs the small state well; in the Discourses, the
durable large state is a republic with distributed authority. Fulcrum encodes
the pair as one structural rule grounded in the light-cone axiom rather than
preference: below the Dunbar horizon (about 150 people) a single centre's
light cone covers the whole organisation, escalating to the centre is a
conversation rather than a queue and clean concentration is priced gently.
Above the horizon the centre exceeds its causal reach; the cost of escalating
to it grows with the implied depth between the centre and the work, which
grows with the log of the population, so the same concentrated structure is
priced progressively harder and distributed authority is preferred.

The amplification saturates at a ceiling: princes do survive at the top of
large organisations (survivorship), rarer with every decade of scale, so
concentration at any size stays a graded penalty and never a prohibition.

The factor prices only clean concentration. Contested ownership is never
forgiven at any scale: a second claimant breaks the authority worldline
whether the organisation is eight people or eighty thousand, so contest
keeps its full price below the horizon and amplifies above it.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log10

from fulcrum.domain.hierarchy import (
    domain_subtree_ids,
    total_headcount,
)
from fulcrum.domain.models import OrgState, Team
from fulcrum.domain.parameters import SimulationParameters
from fulcrum.domain.populations import headcounts_by_domain

_UNIT: float = 1.0
_NO_INFLOW: float = 0.0


def frame_headcount(org: OrgState) -> int:
    """People in the scored frame: unit populations or team sizes rolled up.

    A focused or aggregate frame carries its real population on its nodes
    (a rolled unit node holds its subtree's people), so every frame is
    priced at its own scale: a Dunbar-sized pocket deep inside a large
    organisation may still be run as a principality while the frames above
    it demand a republic.
    """
    return total_headcount(org)


def prince_scale_factor(headcount: int, params: SimulationParameters) -> float:
    """The multiplier on clean-concentration costs at this population.

    Constant and attenuated up to the Dunbar horizon, rising linearly to
    parity across the band, then growing with the log of the population
    above the band, capped at the survivor ceiling.
    """
    if headcount <= params.dunbar_headcount:
        return params.prince_attenuation
    if headcount < params.prince_band_upper:
        band = float(params.prince_band_upper - params.dunbar_headcount)
        progress = (headcount - params.dunbar_headcount) / band
        return (
            params.prince_attenuation + (_UNIT - params.prince_attenuation) * progress
        )
    amplified = _UNIT + params.prince_amplification * log10(
        headcount / params.prince_band_upper
    )
    return min(amplified, params.prince_survivor_ceiling)


def contest_scale_factor(factor: float) -> float:
    """Contest is never forgiven: attenuation does not apply, amplification does."""
    return max(_UNIT, factor)


def scaled_authority_penalty(params: SimulationParameters, factor: float) -> float:
    """The capacity multiplier for a team without local authority, at scale.

    At factor 1 this is exactly the flat authority_penalty; below 1 the
    penalty shrinks toward none; above 1 it deepens. The survivor-ceiling
    validation on SimulationParameters keeps the result strictly positive.
    """
    return _UNIT - (_UNIT - params.authority_penalty) * factor


def scaled_contested_penalty(params: SimulationParameters, factor: float) -> float:
    """The capacity multiplier for a contested team, at scale.

    Contest keeps its full flat price up to the band (attenuation never
    reaches it) and above the band it deepens in proportion to the scaled
    escalation price, so a contested team's capacity sits strictly below a
    merely escalating team's at every scale: the meta-question of who
    decides travels the same distance the decision does, then costs more.
    """
    scaled = scaled_authority_penalty(params, factor)
    ratio = params.contested_penalty / params.authority_penalty
    return min(params.contested_penalty, scaled * ratio)


@dataclass(frozen=True, slots=True)
class ScaleContext:
    """Per-team scale pricing for one scored frame.

    factors holds each team's pricing factor: a clean escalating team is
    priced at its resolution neighbourhood's population, a contested team
    at the frame's contest factor and everyone else at the frame factor.
    inflow holds the escalated arrivals landing on each clean authority's
    queue. unowned holds each clean sovereign's count of unowned
    interfaces: dependencies to other sovereigns with no shared enclosing
    domain, so no institutional roof exists to arbitrate their conflicts.
    frame_factor is the prince factor at the frame's population.
    """

    factors: dict[str, float]
    inflow: dict[str, float]
    unowned: dict[str, int]
    frame_factor: float


# A roof needs an officer: at least one clean authority beyond the edge's
# own endpoints must sit in the shared subtree to convene resolution.
_MIN_DISTINCT_OFFICERS: int = 1


def _unowned_interface_counts(org: OrgState, claimed: set[str]) -> dict[str, int]:
    """Per-team count of sovereign-to-sovereign edges with no working roof.

    Both endpoints must hold clean local authority: an edge touching an
    escalating team already resolves along that team's line, so only two
    sovereigns can face each other with nobody above them. A shared
    enclosing domain counts as a roof only when its subtree holds a clean
    authority beyond the two endpoints themselves: an institution needs at
    least one officer, so two sovereigns alone under a nominal roof are
    still unowned. A loose team shares no domain with anyone.
    """
    ancestors: dict[str, list[str]] = {}
    parent_of = {d.id: d.parent_id for d in org.domains}
    for domain in org.domains:
        chain: list[str] = []
        current: str | None = domain.id
        while current is not None:
            chain.append(current)
            current = parent_of.get(current)
        ancestors[domain.id] = chain
    # Endpoint sovereignty is structural (a claim does not dissolve the
    # unowned edge: contest never repairs fragmentation), while an officer
    # must be clean: a contested authority cannot convene resolution.
    sovereign = {t.id: t.domain_id for t in org.teams if t.has_local_authority}
    officers = {
        team_id: domain_id
        for team_id, domain_id in sovereign.items()
        if team_id not in claimed
    }
    counts = {t.id: 0 for t in org.teams}
    empty: list[str] = []
    officer_counts: dict[str, int] = {}
    for dep in org.internal_dependencies():
        if dep.upstream not in sovereign or dep.downstream not in sovereign:
            continue
        up_chain = ancestors.get(sovereign[dep.upstream] or "", empty)
        down_roof = set(ancestors.get(sovereign[dep.downstream] or "", empty))
        roof = next((d for d in reversed(up_chain) if d in down_roof), None)
        if roof is not None:
            if roof not in officer_counts:
                inside = domain_subtree_ids(org, roof)
                officer_counts[roof] = sum(
                    1 for tid, did in officers.items() if did in inside
                )
            endpoint_officers = (dep.upstream in officers) + (
                dep.downstream in officers
            )
            if officer_counts[roof] - endpoint_officers >= _MIN_DISTINCT_OFFICERS:
                continue
        counts[dep.upstream] += 1
        counts[dep.downstream] += 1
    return counts


def _authority_marked_domains(org: OrgState, clean_authorities: list[Team]) -> set[str]:
    """Domains whose subtree holds a clean authority: each authority marks
    its own domain and every ancestor, so a walk up from an escalating team
    stops at the nearest enclosing unit that can resolve for it."""
    parent_of = {d.id: d.parent_id for d in org.domains}
    marked: set[str] = set()
    for team in clean_authorities:
        current = team.domain_id
        while current is not None and current not in marked:
            marked.add(current)
            current = parent_of.get(current)
    return marked


def scale_context(org: OrgState, params: SimulationParameters) -> ScaleContext:
    """Build the per-team scale pricing for a frame.

    Resolution neighbourhoods: an escalating team resolves at the nearest
    enclosing unit whose subtree holds a clean (uncontested, authoritative)
    team, standing in for the line it escalates to. Its concentration
    charges are priced at that unit's population, so a pocket whose lead
    sits across the desk is forgiven whatever the whole organisation
    weighs, and escalation_load_share of its workload lands on that unit's
    clean authorities: the singularity is a queue and it prices itself.
    The shed load is never attenuated by the prince band (the band forgives
    friction, not bandwidth) and it follows the wiring: an escalating team
    sheds to the resolving authorities it actually has dependencies with,
    so an unconnected authority absorbs nothing and cannot launder a
    saturated centre; wiring it in costs coupling on both ends. Only an
    escalator with no edge to any resolving authority falls back to an
    equal split across the scope's authorities. A team with no resolving
    unit up its chain resolves at the frame itself; when no clean authority
    exists anywhere it sheds nothing and its own capacity cut carries the
    cost. Contest is priced at the frame's contest factor: a claim is
    org-visible, not neighbourhood-local.
    """
    frame_factor = prince_scale_factor(total_headcount(org), params)
    claimed = {c.subject for c in org.claims}
    unowned = _unowned_interface_counts(org, claimed)
    clean_authorities = [
        t for t in org.teams if t.has_local_authority and t.id not in claimed
    ]
    factors: dict[str, float] = {}
    inflow: dict[str, float] = {t.id: _NO_INFLOW for t in org.teams}
    marked = _authority_marked_domains(org, clean_authorities)
    parent_of = {d.id: d.parent_id for d in org.domains}
    # One bottom-up pass prices every resolution neighbourhood; the per-team
    # loop then reads populations from it instead of rescanning the org.
    populations = headcounts_by_domain(org)
    groups: dict[str | None, list[str]] = {}
    for team in org.teams:
        contested = team.id in claimed
        if contested:
            factors[team.id] = contest_scale_factor(frame_factor)
            if team.has_local_authority:
                continue
        elif team.has_local_authority:
            factors[team.id] = frame_factor
            continue
        # An escalating team sheds whether or not it is also contested: a
        # claim never lightens a queue, it only disputes who clears it.
        scope = team.domain_id
        while scope is not None and scope not in marked:
            scope = parent_of.get(scope)
        if not contested:
            if scope is None:
                factors[team.id] = frame_factor
            else:
                factors[team.id] = prince_scale_factor(populations[scope], params)
        groups.setdefault(scope, []).append(team.id)
    shed = params.escalation_load_share * org.workload
    neighbours: dict[str, set[str]] = {}
    for dep in org.internal_dependencies():
        neighbours.setdefault(dep.upstream, set()).add(dep.downstream)
        neighbours.setdefault(dep.downstream, set()).add(dep.upstream)
    # The queue lands where the line points whether or not that line is
    # contested: a claim on the receiving authority disputes who clears
    # the work, it never makes the work disappear, so a blanket overlay
    # cannot drain the centre's queue by contesting it.
    line_authorities = [t for t in org.teams if t.has_local_authority]
    for scope, escalators in groups.items():
        if scope is None:
            recipients = line_authorities
        else:
            inside = domain_subtree_ids(org, scope)
            recipients = [t for t in line_authorities if t.domain_id in inside]
        if not recipients:
            continue
        recipient_ids = {t.id for t in recipients}
        unwired = 0
        for team_id in escalators:
            wired = sorted(neighbours.get(team_id, set()) & recipient_ids)
            if wired:
                per_recipient = shed / len(wired)
                for recipient_id in wired:
                    inflow[recipient_id] += per_recipient
            else:
                unwired += 1
        if unwired:
            per_recipient = shed * unwired / len(recipients)
            for recipient in recipients:
                inflow[recipient.id] += per_recipient
    return ScaleContext(
        factors=factors,
        inflow=inflow,
        unowned=unowned,
        frame_factor=frame_factor,
    )
