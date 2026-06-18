"""Tests for the book showcase assembled for the Help dialog."""

from fulcrum.application.books import BookShowcase, build_book_showcase
from fulcrum.domain.books import COMPLETE_SERIES_EDITION, DA_SERIES


def test_showcase_features_the_hardback_over_the_series():
    showcase = build_book_showcase()
    assert isinstance(showcase, BookShowcase)
    assert showcase.featured == COMPLETE_SERIES_EDITION
    assert showcase.series == DA_SERIES


def test_showcase_intro_is_present_and_names_the_series():
    showcase = build_book_showcase()
    assert showcase.intro
    assert "Decision Architecture" in showcase.intro
