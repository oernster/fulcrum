# Pre-registration: external validation of the Fulcrum structural score

This document fixes the protocol and acceptance thresholds for the external,
blind validation of Fulcrum's structural score before any outcome data is
collected or any organisation is scored under it. It is written for deposit
with the Open Science Framework (osf.io), so that the record of the bar being
set in advance carries a timestamp the author cannot edit. No organisation has
been modelled or scored under this protocol at the time of writing.

## Hypothesis

Fulcrum's deterministic structural score, computed from an organisation's
formal structure alone (teams, dependencies, authority placement, incentive
skew), predicts independently documented structural outcomes better than
chance: organisations with sustained delivery at scale score higher than
organisations with documented delivery collapse.

## Frozen model

The model under test is the scoring function in
`fulcrum/domain/simulation.py` with the default `SimulationParameters`
published there, at the release tag named in the registry deposit. Any change
to a coefficient or to the scoring mechanics after deposit constitutes a new
model and requires a fresh registration; results under a changed model cannot
be reported against this one.

## Design

1. **Case assembly.** Assemble a set of real organisations whose structural
   outcomes are independently documented: sustained delivery at scale on one
   side, delivery collapse or a structural post-mortem on the other. The
   outcome record for every case is fixed and archived before any modelling
   begins.
2. **Blind modelling.** A modeller who does not know the outcome
   classification builds each organisation's Fulcrum model from structural
   facts alone: the org chart, the dependency map and the authority placement
   as they stood at the time. The modeller has no access to the outcome
   record.
3. **Single scoring run.** Each model is scored once. No re-modelling after
   seeing a result.
4. **Analysis.** Per the thresholds below, computed exactly as stated.

## Sample

Minimum 12 organisations with at least 5 in each outcome class. Below this
floor the test is underpowered and is not run; a smaller sample produces no
reportable result in either direction.

## Primary statistic and thresholds

The primary test is a one-sided Mann-Whitney U comparing the scores of the
sustained class against the collapsed class, direction: sustained higher.
AUC denotes the probability that a randomly chosen sustained organisation
outscores a randomly chosen collapsed one (the U statistic normalised).

- **Support:** p < 0.05 and AUC >= 0.75.
- **Falsifying evidence:** AUC <= 0.5 at the sample floor or above; the score
  performs at or below chance.
- **Inconclusive:** anything between. Reported as such, not as support.

## Blinding and conflicts

Cases where the author holds inside knowledge of the organisation are either
excluded or flagged at assembly time; a flagged case is included only if the
modelling is done by someone else and the analysis is reported both with and
without the flagged cases.

## Reporting

The result is published in the Fulcrum repository regardless of outcome,
including the full case list, the archived outcome record, every model file
and the analysis script, so the run is reproducible end to end.
