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

from math import log10

from fulcrum.domain.hierarchy import total_headcount
from fulcrum.domain.models import OrgState
from fulcrum.domain.parameters import SimulationParameters

_UNIT: float = 1.0


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
