"""The book showcase rendered by the Help dialog: a featured edition plus series.

The dialog is a client of this application surface rather than of the domain
directly, mirroring the glossary. It adds the short intro shown above the covers
and marks the hardback as the featured edition, leaving the four volumes as the
series the dialog lays out below it.
"""

from __future__ import annotations

from dataclasses import dataclass

from fulcrum.domain.books import COMPLETE_SERIES_EDITION, DA_SERIES, BookEntry

_INTRO = (
    "Fulcrum scores organisations with a model whose moves, signals and core "
    "ideas come from the Decision Architecture series by Oliver Ernster. The "
    "four volumes build the thinking the game puts into play; the hardback "
    "collects all four in one reference edition."
)


@dataclass(frozen=True, slots=True)
class BookShowcase:
    """What the Help dialog shows: intro text, the featured edition and series."""

    intro: str
    featured: BookEntry
    series: tuple[BookEntry, ...]


def build_book_showcase() -> BookShowcase:
    """Assemble the book showcase for the Help > Book background dialog."""
    return BookShowcase(
        intro=_INTRO,
        featured=COMPLETE_SERIES_EDITION,
        series=DA_SERIES,
    )
