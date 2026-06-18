"""The Decision Architecture books behind Fulcrum's model (static reference data).

Fulcrum scores organisations with a model whose moves, signals and core ideas
come from Oliver Ernster's Decision Architecture series. This module is the
single in-app source of truth for the four series volumes and the combined
hardback edition, so the Help dialog (and any later surface) renders the same
authored titles, blurbs and links. It is pure data with no I/O and no Qt; the
cover image is referenced only by filename so the UI layer can resolve it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BookEntry:
    """One book: its title, cover image filename, a one-line blurb and a link."""

    title: str
    cover_filename: str
    blurb: str
    amazon_uk_url: str


# The four volumes of the series, in reading order. Titles, blurbs and links are
# the authored values from the crankthecode catalogue; cover_filename names the
# PNG bundled under assets/books/.
DA_SERIES: tuple[BookEntry, ...] = (
    BookEntry(
        title="Decision Architecture",
        cover_filename="_cover_da.png",
        blurb="How technical organisations fail and recover",
        amazon_uk_url="https://www.amazon.co.uk/dp/B0GT4JNMGK",
    ),
    BookEntry(
        title="Decision Architecture Patterns",
        cover_filename="_cover_da_patterns.png",
        blurb="Structural patterns that recur across technical organisations",
        amazon_uk_url="https://www.amazon.co.uk/dp/B0GT4CZ327",
    ),
    BookEntry(
        title="Decision Architecture: The Move Space",
        cover_filename="_cover-da-move-space.png",
        blurb="A Positional Model of Organisational Change",
        amazon_uk_url="https://www.amazon.co.uk/dp/B0GTDX7186",
    ),
    BookEntry(
        title="Relativistic Decision Architecture",
        cover_filename="_cover_relativistic_da_architecture.png",
        blurb="The geometry of decision systems",
        amazon_uk_url="https://www.amazon.co.uk/dp/B0GT7D4P8G",
    ),
)


# The combined hardback: rendered as the featured edition, not a fifth peer in
# the series grid.
COMPLETE_SERIES_EDITION: BookEntry = BookEntry(
    title="Decision Architecture Series",
    cover_filename="hardback_cover.png",
    blurb="All four volumes combined into a single hardback reference edition",
    amazon_uk_url="https://www.amazon.co.uk/dp/B0GTMVV8T5",
)
