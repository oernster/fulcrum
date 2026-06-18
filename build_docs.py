#!/usr/bin/env python3
"""Generate the Fulcrum GitHub Pages site under docs/ from the app's own data.

This is a build step, not a site generator or CMS: it emits a plain static
index.html the same way buildexe.py emits a binary. The books section is
rendered from the exact showcase the in-app Help dialog uses
(fulcrum.application.books) and the identity comes from fulcrum.version, so the
site cannot drift from the app. The stylesheet (docs/styles.css) is a static
sibling and the screenshots live in docs/assets/screenshots/.

Run from the repo root:

    python build_docs.py
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from PIL import Image

from fulcrum.application.books import BookShowcase, build_book_showcase
from fulcrum.domain.books import BookEntry
from fulcrum.version import APP_COPYRIGHT, APP_NAME, __version__

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"
BOOK_ASSETS = ASSETS / "books"
ICON_SOURCE = ROOT / "fulcrum.png"
BOOK_COVER_SOURCE = ROOT / "assets" / "books"

REPO_URL = "https://github.com/oernster/fulcrum"
RELEASES_URL = f"{REPO_URL}/releases"
SITE_URL = "https://oernster.github.io/fulcrum/"
BOOKS_URL = "https://www.crankthecode.com/books"
AUTHOR_URL = "https://www.crankthecode.com/"

ICON_REL = "assets/fulcrum.png"
BOARD_SHOT = "assets/screenshots/play-board.png"
GUIDE_SHOT = "assets/screenshots/play-guide.png"
BOOK_COVER_REL = "assets/books"
LINK_TEXT = "View on Amazon UK"
SITE_TAGLINE = "Organisational Decision Architecture sandbox"

# Covers and the icon ship downscaled: they are shown at most ~190px wide, so a
# web-sized copy keeps the page light instead of serving multi-megabyte art.
ICON_WEB_PX = 256
COVER_MAX_WIDTH = 440
COVER_MAX_HEIGHT = 1600
_LANCZOS = Image.Resampling.LANCZOS

_FEATURES = (
    (
        "01",
        "Structural moves",
        "Delegate authority, stabilise interfaces, realign incentives or "
        "collapse a boundary. Every move is scored from blunder to great.",
    ),
    (
        "02",
        "Signals to watch",
        "Handoff queue age, escalations, rework and influence without "
        "authority: the lagging indicators, each with its own definition.",
    ),
    (
        "03",
        "A guide to a stronger org",
        "Ask for the guide and the planner shows a move-by-move line from "
        "where you are to a stronger score, the way an engine shows its line.",
    ),
    (
        "04",
        "Yours, on your machine",
        "Generate a level, model your own organisation or import one as JSON. "
        "There is no account and no server; nothing leaves your machine.",
    ),
)


def _feature_html() -> str:
    cards = []
    for number, title, body in _FEATURES:
        cards.append(
            '<div class="feature">'
            f'<div class="fnum">{number}</div>'
            f"<h3>{escape(title)}</h3>"
            f"<p>{escape(body)}</p>"
            "</div>"
        )
    return "".join(cards)


def _cover(book: BookEntry) -> str:
    return (
        f'<img loading="lazy" src="{BOOK_COVER_REL}/{book.cover_filename}" '
        f'alt="{escape(book.title)} cover">'
    )


def _buy(book: BookEntry, css_class: str, arrow: str) -> str:
    return f'<a class="{css_class}" href="{book.amazon_uk_url}">{LINK_TEXT}{arrow}</a>'


def _featured_html(book: BookEntry) -> str:
    return (
        '<div class="featured">'
        f"{_cover(book)}"
        '<div class="meta">'
        '<div class="kicker">The complete series</div>'
        f"<h3>{escape(book.title)}</h3>"
        f"<p>{escape(book.blurb)}</p>"
        f"{_buy(book, 'btn btn-primary', '')}"
        "</div></div>"
    )


def _series_html(books: tuple[BookEntry, ...]) -> str:
    cards = []
    for book in books:
        cards.append(
            '<div class="book">'
            f"{_cover(book)}"
            f"<h4>{escape(book.title)}</h4>"
            f"<p>{escape(book.blurb)}</p>"
            f"{_buy(book, 'buy', ' &rarr;')}"
            "</div>"
        )
    return f'<div class="series">{"".join(cards)}</div>'


def _head(description: str) -> str:
    return f"""<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{APP_NAME}: a Decision Architecture sandbox</title>
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{SITE_URL}">
<meta property="og:type" content="website">
<meta property="og:title" content="{APP_NAME}: {SITE_TAGLINE}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:url" content="{SITE_URL}">
<meta property="og:image" content="{SITE_URL}{BOARD_SHOT}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="{ICON_REL}">
<link rel="stylesheet" href="styles.css">
</head>"""


def _nav() -> str:
    return f"""<header class="nav">
  <div class="container nav-inner">
    <a class="brand" href="#top">
      <img src="{ICON_REL}" alt="{APP_NAME} icon">{APP_NAME}</a>
    <nav class="nav-links">
      <a href="#overview">Overview</a>
      <a href="#play">Play by play</a>
      <a href="#books">The books</a>
      <a href="{REPO_URL}">GitHub</a>
    </nav>
  </div>
</header>"""


def _hero() -> str:
    return f"""<section class="hero">
    <div class="container">
      <img class="logo" src="{ICON_REL}" alt="{APP_NAME} icon">
      <h1>{APP_NAME}</h1>
      <div class="tagline">{SITE_TAGLINE}</div>
      <p class="lede">The Decision Architecture series, made playable. Fix a
        failing organisation with structural moves; a deterministic model
        scores the result from 0 to 100.</p>
      <div class="cta">
        <a class="btn btn-primary" href="{RELEASES_URL}">Download</a>
        <a class="btn btn-ghost" href="#books">Explore the books</a>
      </div>
      <p class="release-note">Builds are published on the
        <a href="{RELEASES_URL}">releases page</a> as they ship.</p>
      <div class="badges">
        <span>Local-first</span>·<span>No cloud, no account</span>
        ·<span>GPL-3.0 + LGPL-3.0</span>
      </div>
    </div>
  </section>"""


def _overview() -> str:
    return f"""<section id="overview">
    <div class="container">
      <div class="eyebrow">The model, made incarnate</div>
      <h2 class="section-title">A model you can hold</h2>
      <p class="section-sub">Decision Architecture argues that organisations
        fail structurally, not for lack of effort. {APP_NAME} turns that
        argument into an engine you operate directly: the decision objects,
        authority worldlines and structural moves from the books, scored
        live.</p>
      <div class="features">{_feature_html()}</div>
    </div>
  </section>"""


def _play() -> str:
    board_alt = f"The {APP_NAME} board scoring a failing org"
    guide_alt = f"The {APP_NAME} guide planning a recovery"
    return f"""<section id="play" class="alt">
    <div class="container">
      <div class="eyebrow">Play by play</div>
      <h2 class="section-title">Watch a failing org recover</h2>
      <p class="section-sub">Load an organisation and the board scores its
        structural health, maps who decides locally against who escalates and
        lists every move open to you.</p>
      <div class="shots">
        <figure class="shot">
          <div class="frame">
            <div class="bar"><i></i><i></i><i></i></div>
            <img loading="lazy" src="{BOARD_SHOT}" alt="{board_alt}">
          </div>
          <figcaption><b>The position.</b> A seven-team enterprise scoring
            24.5 out of 100. Stick figures mark who decides locally against who
            escalates; the chips surface where it hurts, including influence
            without authority.</figcaption>
        </figure>
        <figure class="shot">
          <div class="frame">
            <div class="bar"><i></i><i></i><i></i></div>
            <img loading="lazy" src="{GUIDE_SHOT}" alt="{guide_alt}">
          </div>
          <figcaption><b>The line.</b> The guide plans the recovery move by
            move, 24.5 to 85.1, each step classified from blunder to great. It
            opens by delegating authority to the teams everyone depends
            on.</figcaption>
        </figure>
      </div>
    </div>
  </section>"""


def _books(showcase: BookShowcase) -> str:
    return f"""<section id="books">
    <div class="container">
      <div class="eyebrow">The foundation</div>
      <h2 class="section-title">Built on the Decision Architecture series</h2>
      <p class="books-intro">{escape(showcase.intro)}</p>
      {_featured_html(showcase.featured)}
      {_series_html(showcase.series)}
    </div>
  </section>"""


def _footer() -> str:
    return f"""<footer>
  <div class="container footer-inner">
    <div>
      <strong>{APP_NAME}</strong>: {SITE_TAGLINE}<br>
      {escape(APP_COPYRIGHT)} · Local-first · GPL-3.0 + LGPL-3.0 · v{__version__}
    </div>
    <div class="footer-links">
      <a href="{RELEASES_URL}">Releases</a>
      <a href="{REPO_URL}">GitHub</a>
      <a href="{BOOKS_URL}">The books</a>
      <a href="{AUTHOR_URL}">crankthecode.com</a>
    </div>
  </div>
</footer>"""


def _page_html(showcase: BookShowcase) -> str:
    description = (
        f"{APP_NAME} turns the Decision Architecture series into a playable "
        "model: fix a failing organisation with structural moves and a "
        "deterministic engine scores the result from 0 to 100."
    )
    return (
        '<!DOCTYPE html>\n<html lang="en">\n'
        + _head(description)
        + "\n<body>\n"
        + _nav()
        + '\n<main id="top">\n  '
        + _hero()
        + "\n  "
        + _overview()
        + "\n  "
        + _play()
        + "\n  "
        + _books(showcase)
        + "\n</main>\n"
        + _footer()
        + "\n</body>\n</html>\n"
    )


def _save_icon() -> None:
    with Image.open(ICON_SOURCE) as img:
        icon = img.convert("RGBA")
    icon.thumbnail((ICON_WEB_PX, ICON_WEB_PX), _LANCZOS)
    icon.save(ASSETS / "fulcrum.png", optimize=True)


def _save_cover(book: BookEntry) -> None:
    with Image.open(BOOK_COVER_SOURCE / book.cover_filename) as img:
        img.thumbnail((COVER_MAX_WIDTH, COVER_MAX_HEIGHT), _LANCZOS)
        img.save(BOOK_ASSETS / book.cover_filename, optimize=True)


def _copy_assets(showcase: BookShowcase) -> None:
    BOOK_ASSETS.mkdir(parents=True, exist_ok=True)
    _save_icon()
    for book in (showcase.featured, *showcase.series):
        _save_cover(book)


def main() -> int:
    showcase = build_book_showcase()
    _copy_assets(showcase)
    (DOCS / "index.html").write_text(_page_html(showcase), encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print(f"[build_docs] wrote {DOCS / 'index.html'}")
    print(f"[build_docs] {1 + len(showcase.series)} covers + icon copied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
