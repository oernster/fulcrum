"""Tests for the Decision Architecture book reference data."""

from dataclasses import FrozenInstanceError

import pytest

from fulcrum.domain.books import COMPLETE_SERIES_EDITION, DA_SERIES, BookEntry

_AMAZON_PREFIX = "https://www.amazon.co.uk/dp/"
_PNG_SUFFIX = ".png"
_EXPECTED_SERIES = 4


def test_series_has_the_four_volumes_with_complete_fields():
    assert len(DA_SERIES) == _EXPECTED_SERIES
    for book in DA_SERIES:
        assert isinstance(book, BookEntry)
        assert book.title
        assert book.blurb
        assert book.cover_filename.endswith(_PNG_SUFFIX)
        assert book.amazon_uk_url.startswith(_AMAZON_PREFIX)


def test_series_titles_and_covers_are_distinct():
    titles = [book.title for book in DA_SERIES]
    covers = [book.cover_filename for book in DA_SERIES]
    assert len(set(titles)) == len(titles)
    assert len(set(covers)) == len(covers)


def test_complete_series_edition_is_the_hardback():
    assert COMPLETE_SERIES_EDITION.title == "Decision Architecture Series"
    assert "hardback" in COMPLETE_SERIES_EDITION.blurb
    assert COMPLETE_SERIES_EDITION.cover_filename == "hardback_cover.png"
    assert COMPLETE_SERIES_EDITION.amazon_uk_url.startswith(_AMAZON_PREFIX)


def test_book_entry_is_immutable():
    with pytest.raises(FrozenInstanceError):
        DA_SERIES[0].title = "changed"
