"""Tests for the decision glossary content builder."""

import pytest

from fulcrum.application.glossary import (
    TERM_DEPENDENCY,
    TERM_DOMAIN,
    TERM_ESCALATION,
    TERM_INCENTIVE_SKEW,
    TERM_LOCAL_AUTHORITY,
    TERM_MOVE_CLASSIFICATION,
    TERM_PROPAGATION_DELAY,
    TERM_STRUCTURAL_HEALTH,
    TERM_TEAM_SIZE,
    TERM_WORKLOAD,
    build_glossary,
    short_help,
)
from fulcrum.domain.moves import MoveKind
from fulcrum.domain.signals import SIGNAL_DEFINITIONS


def test_glossary_has_sections_for_moves_signals_and_ideas():
    sections = build_glossary()
    headings = [heading for heading, _ in sections]
    assert headings == ["Moves", "Signals to watch", "Core ideas"]
    by_heading = {heading: entries for heading, entries in sections}
    assert len(by_heading["Moves"]) == len(MoveKind)
    assert len(by_heading["Signals to watch"]) == len(SIGNAL_DEFINITIONS)
    assert by_heading["Core ideas"]


def test_glossary_move_terms_and_text_are_readable():
    moves = dict(build_glossary()[0][1])
    assert "Collapse boundary" in moves
    assert "not centralisation" in moves["Collapse boundary"]


def test_short_help_covers_every_concept_term():
    keys = (
        TERM_LOCAL_AUTHORITY,
        TERM_ESCALATION,
        TERM_DEPENDENCY,
        TERM_PROPAGATION_DELAY,
        TERM_DOMAIN,
        TERM_INCENTIVE_SKEW,
        TERM_TEAM_SIZE,
        TERM_STRUCTURAL_HEALTH,
        TERM_MOVE_CLASSIFICATION,
        TERM_WORKLOAD,
    )
    for key in keys:
        assert short_help(key)


def test_short_help_covers_every_signal():
    for definition in SIGNAL_DEFINITIONS:
        assert short_help(definition.key)


def test_short_help_rejects_unknown_keys():
    with pytest.raises(KeyError):
        short_help("nonsense")


def test_incentive_skew_short_help_uses_a_concrete_example():
    assert "tickets closed" in short_help(TERM_INCENTIVE_SKEW)
