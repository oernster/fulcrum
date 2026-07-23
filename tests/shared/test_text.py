"""Tests for the shared text helpers."""

from fulcrum.shared.text import count_noun


def test_count_noun_singular_and_regular_plural():
    assert count_noun(1, "team") == "1 team"
    assert count_noun(2, "team") == "2 teams"
    assert count_noun(0, "team") == "0 teams"


def test_count_noun_irregular_plural():
    assert count_noun(1, "person", "people") == "1 person"
    assert count_noun(5, "person", "people") == "5 people"


def test_count_noun_formats_thousands():
    assert count_noun(1200, "person", "people") == "1,200 people"
