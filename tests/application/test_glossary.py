"""Tests for the decision glossary content builder."""

from fulcrum.application.glossary import build_glossary
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
