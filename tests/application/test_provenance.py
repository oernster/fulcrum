"""Tests for the in-app provenance of every model number."""

from dataclasses import fields, replace

from fulcrum.application.provenance import (
    build_provenance,
    fragility_text,
    intro_text,
)
from fulcrum.domain.parameters import DEFAULT_PARAMETERS, DEFAULT_THRESHOLDS


def test_every_simulation_parameter_is_accounted_for():
    """No coefficient may exist without a provenance entry naming it.

    This is the page's own honesty gate: adding a parameter without
    accounting for it here fails the build.
    """
    terms = " ".join(entry.term for entry in build_provenance())
    for field in fields(DEFAULT_PARAMETERS):
        assert field.name in terms, field.name


def test_every_entry_carries_a_full_account():
    for entry in build_provenance():
        assert entry.term
        assert entry.does
        assert entry.mechanism
        assert entry.magnitude


def test_values_are_read_live_from_the_parameters():
    """A changed coefficient must change the page: no hardcoded copies."""
    changed = replace(DEFAULT_PARAMETERS, authority_penalty=0.41)
    terms = " ".join(e.term for e in build_provenance(changed))
    assert "authority_penalty = 0.41" in terms
    default_terms = " ".join(e.term for e in build_provenance())
    assert (
        f"authority_penalty = {DEFAULT_PARAMETERS.authority_penalty}" in default_terms
    )


def test_thresholds_and_move_constants_are_present():
    terms = " ".join(e.term for e in build_provenance())
    assert f"+{DEFAULT_THRESHOLDS.great_delta}" in terms
    assert "approval gate delay" in terms
    assert "consultation delay" in terms


def test_framing_states_the_honest_split():
    assert "engineering judgement" in intro_text().lower()
    assert "sensitivity" in fragility_text().lower()
