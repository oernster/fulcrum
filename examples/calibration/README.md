# Calibration organisations

This directory holds organisations modelled with knowledge of their real
outcomes, scored by `python calibrate.py` from the repository root. Each
case pairs a structural model with an expected score band that encodes the
modeller's claim about how the organisation actually functioned; the runner
flags every case whose score lands outside its band, so the coefficients
are held to lived outcomes rather than to taste.

## How to add a case

1. Copy `TEMPLATE.json` to a new file named after the case.
2. Model the structure as it stood at the time: teams with real headcounts
   and honest `has_local_authority`, dependencies with their real waiting
   times, the domain hierarchy (a shared roof is a claim that a real
   arbitrating owner existed), and any second reporting lines or chapters
   as claims.
3. Set the `calibration` block: a short label, the expected band and one
   sentence on what actually happened. The band should be written before
   looking at the score; it is the claim under test.
4. Run `python calibrate.py`. A MISS is information either way: the model
   is mispricing that shape, or the model disagrees with the memory and
   the disagreement is worth examining.

Sizes worth covering: a handful of small organisations (under 150 people),
several mid-sized (150 to 2,000) and at least a few large ones, with both
good and bad outcomes at each size, so the calibration exercises the prince
band on both sides of the Dunbar horizon.

## These cases can never join the validation set

The preregistered external validation (PREREGISTRATION.md) requires blind
modelling: the modeller must not know the outcome. Every case here is
modelled with outcome knowledge, so calibration cases are permanently
ineligible for that set. Calibration tunes the prior; validation tests it.

## Seed cases

The three shipped cases are synthetic references marking the shapes the
model prices deliberately: an empowered small agency (scores well), a
founder with eighteen squads across three tribes escalating to them
(strained: the queue is visible even below the Dunbar horizon) and a
matrixed enterprise of about six thousand people whose unit and sub-unit
leadership is claimed by the matrix on a delayed dependency chain (the
documented-collapse shape). Every case is a drillable hierarchy whose leaf
teams hold three to eight people with varied sizes. The enterprise case is
written by `generate_matrixed_enterprise.py` at the repository root
(deterministic and seeded), so change that script and rerun it rather than
editing the JSON by hand. Replace or outnumber them with real cases as
they accumulate.
