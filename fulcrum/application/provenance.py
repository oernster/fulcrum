"""Provenance of every number in the model: what, where, why and how fragile.

A CTO meeting the score cold is entitled to ask why 0.45 and not 0.3. This
module answers in-app, coefficient by coefficient, with the honest split the
model page makes: the mechanisms (what is penalised and in which direction)
come from the Decision Architecture books; the magnitudes are engineering
judgement from 28 years across defence, fintech, telecoms and startups,
constrained wherever the code enforces a structural rule. Every value shown
is read live from the parameter objects, so this page can never drift from
the model it describes: a dialog about magic numbers must not contain any.
"""

from __future__ import annotations

from dataclasses import dataclass

from fulcrum.domain.moves import (
    APPROVAL_GATE_DELAY,
    REALIGN_RETENTION,
    STABILISE_RETENTION,
)
from fulcrum.domain.moves_claims import CONSULTATION_DELAY
from fulcrum.domain.parameters import (
    DEFAULT_PARAMETERS,
    DEFAULT_THRESHOLDS,
    ClassificationThresholds,
    SimulationParameters,
)


@dataclass(frozen=True, slots=True)
class ProvenanceEntry:
    """One number's account: value, effect, mechanism source and magnitude."""

    term: str
    does: str
    mechanism: str
    magnitude: str


def intro_text() -> str:
    """The framing: what kind of model this is and the honest split."""
    return (
        "Fulcrum is a hand-tuned evaluation function: an expert prior "
        "encoded as one deterministic scoring rule, the way a chess "
        "engine's classical evaluation was hand-tuned by strong players "
        "for years. Every coefficient lives in one frozen dataclass "
        "(SimulationParameters); there are no hidden constants and the "
        "values below are read live from it, so this page cannot drift "
        "from the model. The honest split: the mechanisms (what is "
        "penalised and in which direction) come from the Decision "
        "Architecture books; the magnitudes (the specific numbers) are "
        "engineering judgement from 28 years across defence, fintech, "
        "telecoms and startups, constrained where the code enforces a "
        "structural rule. A page claiming every number was derived from "
        "theory would not be believed and would not be true."
    )


def fragility_text() -> str:
    """How the numbers are held accountable and where they are fragile."""
    return (
        "Fragility, stated plainly. The qualitative conclusions do not "
        "depend on the exact values: a published sensitivity sweep "
        "(sensitivity.py) perturbs every coefficient by 0.8 and 1.2 and "
        "re-scores the ten example archetypes, and all five conclusions "
        "(both archetype orderings, the typical-versus-well-designed gap "
        "and both blunders staying negative) survive every perturbed "
        "configuration and 100% of 1,000 joint draws. The calibration "
        "harness (calibrate.py) scores organisations with known outcomes "
        "against expected bands drawn from lived experience. What the "
        "sweep cannot buy is validity outside its experience base: the "
        "magnitudes generalise engineering organisations, so a hospital, "
        "a newsroom or a regiment may need different numbers even where "
        "the mechanisms hold. A disputed magnitude is something you "
        "change and rerun, not something you argue about: every value "
        "sits in one published dataclass and every score decomposes into "
        "named penalties."
    )


def build_provenance(
    params: SimulationParameters = DEFAULT_PARAMETERS,
    thresholds: ClassificationThresholds = DEFAULT_THRESHOLDS,
) -> tuple[ProvenanceEntry, ...]:
    """Every number in the model with its account, values read live."""
    return _capacity_entries(params) + _score_entries(params, thresholds)


def _capacity_entries(p: SimulationParameters) -> tuple[ProvenanceEntry, ...]:
    return (
        ProvenanceEntry(
            f"base_capacity = {p.base_capacity}",
            "Decisions a team can clear per turn before penalties; the "
            "scale arrivals are measured against.",
            "Queueing framing: arrivals against capacity.",
            "Engineering judgement.",
        ),
        ProvenanceEntry(
            f"authority_penalty = {p.authority_penalty}",
            "Multiplies a team's decision capacity when it lacks local " "authority.",
            "Decision Architecture (authority before accountability); "
            "Relativistic Decision Architecture, Axiom 2 (authority "
            "worldlines).",
            "Engineering judgement.",
        ),
        ProvenanceEntry(
            f"contested_penalty = {p.contested_penalty}",
            "Multiplies capacity for a team whose decisions carry a "
            "standing claim (matrix and dual reporting); above the prince "
            "band it deepens with the scaled escalation price, so contest "
            "costs strictly more than clean escalation at every scale.",
            "Relativistic Decision Architecture, Axiom 2 refinement: a "
            "worldline that cannot name its owner is broken and the "
            "meta-question is the cost.",
            "Judgement; the ordering against authority_penalty is " "enforced in code.",
        ),
        ProvenanceEntry(
            (
                f"dunbar_headcount = {p.dunbar_headcount}, "
                f"prince_band_upper = {p.prince_band_upper}, "
                f"prince_attenuation = {p.prince_attenuation}, "
                f"prince_amplification = {p.prince_amplification}, "
                f"prince_survivor_ceiling = {p.prince_survivor_ceiling}"
            ),
            "Price clean concentration by scale (the prince band): "
            f"attenuated to {p.prince_attenuation} of the flat price up "
            f"to {p.dunbar_headcount} people, rising to parity across "
            f"the band to {p.prince_band_upper}, then growing with the "
            f"log of the population and capped at "
            f"{p.prince_survivor_ceiling}. Contest is never attenuated, "
            "only amplified.",
            "Machiavelli, The Prince and the Discourses, unified by "
            "scale; Dunbar's number for the horizon; Relativistic "
            "Decision Architecture, Axiom 3 (light cones) and the limits "
            "of control.",
            "Horizon and band edge from Dunbar's number; magnitudes "
            "engineering judgement; the positive-capacity cap on the "
            "ceiling is enforced in code.",
        ),
        ProvenanceEntry(
            f"escalation_load_share = {p.escalation_load_share}",
            "The fraction of an escalating team's workload landing on its "
            "resolving authorities' queues, so a saturated centre prices "
            "itself as latency. Deliberately not attenuated by the prince "
            "band: the band forgives communication friction, never "
            "decision bandwidth.",
            "Decision Architecture (over-centralisation as bottleneck); "
            "LatencyLab's placement result: the singularity is a queue "
            "and it prices itself.",
            "Engineering judgement: a centre saturates at roughly a dozen "
            "escalation lines at typical workloads.",
        ),
        ProvenanceEntry(
            f"dependent_demand_weight = {p.dependent_demand_weight}",
            "Routes demand along dependencies: each team waiting on an "
            "upstream lands this fraction of the frame's workload on the "
            "upstream's queue, authority notwithstanding. An empowered "
            "hub that thirty teams wait on saturates exactly as a "
            "deciding centre does; a light fan-out stays free while "
            "capacity absorbs it, so the cost begins where the queue "
            "does.",
            "Little's law (the shared upstream is a server and its wait "
            "grows with demand); LatencyLab's placement result: the "
            "singularity is a queue and it prices itself, for dependency "
            "concentration as it already did for authority "
            "concentration.",
            "Engineering judgement; held at or below "
            "escalation_load_share (enforced in code), since waiting on "
            "a supplier may never cost more than resolving through an "
            "authority.",
        ),
        ProvenanceEntry(
            f"unowned_interface_weight = {p.unowned_interface_weight}",
            "Prices fragmentation: a dependency between two clean "
            "sovereigns sharing no enclosing domain has no roof under "
            "which its conflicts can be arbitrated, so each such edge "
            "pushes its endpoints toward the cannot-decide-cleanly share.",
            "Machiavelli's Discourses (the republic is institutionalised: "
            "a senate, not merely distributed sovereignty); Decision "
            "Architecture (fragmentation).",
            "Engineering judgement: two unowned interfaces fully "
            "compromise a team's clean-decision standing.",
        ),
        ProvenanceEntry(
            f"coupling_weight = {p.coupling_weight}",
            "Divides capacity per dependency touching the team.",
            "Decision Architecture (latency accumulation); The Move Space "
            "(coordination overload).",
            "Engineering judgement.",
        ),
        ProvenanceEntry(
            f"incentive_weight = {p.incentive_weight}",
            "Divides capacity as the team's incentive skew rises.",
            "Relativistic Decision Architecture, Axiom 5 "
            "(incentive-induced curvature).",
            "Engineering judgement.",
        ),
        ProvenanceEntry(
            f"delay_arrival_weight = {p.delay_arrival_weight}",
            "Inflates a team's effective arrivals per unit of incoming "
            "propagation delay.",
            "Relativistic Decision Architecture, Axiom 4 (causal " "propagation).",
            "Engineering judgement.",
        ),
        ProvenanceEntry(
            (
                f"cognitive_load_weight = {p.cognitive_load_weight}, "
                f"ideal_team_size = {p.ideal_team_size}"
            ),
            "Divides capacity per unit of team size beyond the "
            "comfortable band; zero at or below it, so it never disturbs "
            "an existing position.",
            "Engineering judgement, deliberately gentle.",
            "Engineering judgement.",
        ),
    )


def _score_entries(
    p: SimulationParameters, t: ClassificationThresholds
) -> tuple[ProvenanceEntry, ...]:
    return (
        ProvenanceEntry(
            (
                f"latency_weight = {p.latency_weight}, "
                f"escalation_weight = {p.escalation_weight}, "
                f"rework_weight = {p.rework_weight}"
            ),
            "The composite penalty's three shares: backlog at boundaries, "
            "the fraction of teams that cannot decide locally and mean "
            "incentive skew.",
            "Decision Architecture: decision latency is the first scaling "
            "bottleneck, which justifies latency carrying the largest "
            "share; escalation as the signal of missing authority; Axiom "
            "5 for skew surfacing later as rework.",
            "Judgement; the three shares must sum to 1.0, enforced in " "code.",
        ),
        ProvenanceEntry(
            (
                f"influence_weight = {p.influence_weight}, "
                f"influence_tolerance = {p.influence_tolerance}"
            ),
            "Divides the whole score by the per-team mean of "
            "influence-without-authority load, so one overloaded hub "
            "costs a large organisation a proportionate slice rather "
            "than half its score.",
            "Decision Architecture (delegation without authority); "
            "Decision Architecture Patterns (decision shadow, phantom "
            "authority).",
            "Engineering judgement, gentle by design.",
        ),
        ProvenanceEntry(
            f"contested_weight = {p.contested_weight}",
            "Divides the whole score per standing claim: the structural "
            "owner is claimant one, so each claim is one claimant too "
            "many.",
            "Decision Architecture Patterns (decision semaphore, phantom "
            "authority); Relativistic Decision Architecture: authority "
            "fragmenting within a domain manufactures coordination load.",
            "Engineering judgement, gentle by design.",
        ),
        ProvenanceEntry(
            f"max_score = {p.max_score}",
            "The score's ceiling: the bounded penalties compose into a "
            "0 to this scale.",
            "Presentation choice: a percent-like scale reads instantly.",
            "Structural constant, not a tuned magnitude.",
        ),
        ProvenanceEntry(
            (
                f"Classification bands: great at +{t.great_delta} or "
                f"more, good at +{t.good_delta} or more, blunder at "
                f"{t.blunder_delta} or less"
            ),
            "Turn a move's score delta into a grade from blunder to " "great.",
            "The Move Space: the move taxonomy itself.",
            "Band edges are engineering judgement.",
        ),
        ProvenanceEntry(
            (
                f"Move constants: approval gate delay = "
                f"{APPROVAL_GATE_DELAY}, stabilise retention = "
                f"{STABILISE_RETENTION}, realign retention = "
                f"{REALIGN_RETENTION}, consultation delay = "
                f"{CONSULTATION_DELAY}"
            ),
            "Shape what each move does: a new approval gate arrives with "
            "delay on every team; stabilising and realigning pull values "
            "toward zero without forcing them there; downgrading a claim "
            "prices the consulted party as explicit waiting. The matrix "
            "overlay needs no constant: its damage is pure contest.",
            "The Move Space: the blunder and good-move catalogues.",
            "Engineering judgement.",
        ),
    )
