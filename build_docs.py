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

import json
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
SITE_TAGLINE = "Organisational Decision Architecture Sandbox"
PAGE_TITLE = f"{APP_NAME}: Decision Architecture Sandbox for Architects and CTOs"
THEME_COLOR = "#0d0f12"
SEO_KEYWORDS = (
    "Decision Architecture, organisational design, software architecture, "
    "engineering leadership, CTO, org structure, decision latency, "
    "authority design, technical leadership, principal engineer"
)
AUDIENCE_TYPE = (
    "Software architects, senior and principal engineers, " "CTOs and technical leaders"
)

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

_AUDIENCE = (
    (
        "Software architects",
        "Reason about authority boundaries, coupling and dependency structure "
        "as a system you can score, not a diagram you argue over.",
    ),
    (
        "Senior and principal engineers",
        "See why an organisation slows as it scales and which structural move "
        "removes the bottleneck instead of working around it.",
    ),
    (
        "CTOs and engineering leaders",
        "Test a reorg, a delegation or a boundary change against the model "
        "before you test it on people, then read the trade-off as one number.",
    ),
    (
        "Founders and the C-suite",
        "Make the shape of the organisation legible: where decisions stall, "
        "where authority is missing and where growth will bite.",
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


def _who_html() -> str:
    cards = []
    for title, body in _AUDIENCE:
        cards.append(
            '<div class="feature">'
            f"<h3>{escape(title)}</h3>"
            f"<p>{escape(body)}</p>"
            "</div>"
        )
    return "".join(cards)


def _who() -> str:
    return f"""<section id="who" class="alt">
    <div class="container">
      <div class="eyebrow">Who it is for</div>
      <h2 class="section-title">Built for the people who own structure</h2>
      <p class="section-sub">{APP_NAME} is a thinking tool for the roles that
        answer for how an organisation is shaped and how it decides: software
        architects, senior and principal engineers, CTOs and the wider
        C-suite.</p>
      <div class="features">{_who_html()}</div>
    </div>
  </section>"""


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


def _structured_data(description: str) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": APP_NAME,
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Windows",
        "description": description,
        "url": SITE_URL,
        "image": f"{SITE_URL}{BOARD_SHOT}",
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "GBP"},
        "author": {"@type": "Person", "name": "Oliver Ernster", "url": AUTHOR_URL},
        "audience": {"@type": "Audience", "audienceType": AUDIENCE_TYPE},
        "keywords": SEO_KEYWORDS,
        "license": "https://www.gnu.org/licenses/gpl-3.0.html",
    }
    return (
        '<script type="application/ld+json">'
        + json.dumps(data, ensure_ascii=True)
        + "</script>"
    )


def _head(description: str) -> str:
    image = f"{SITE_URL}{BOARD_SHOT}"
    image_alt = f"The {APP_NAME} board scoring an organisation's structure"
    return f"""<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(PAGE_TITLE)}</title>
<meta name="description" content="{escape(description)}">
<meta name="keywords" content="{escape(SEO_KEYWORDS)}">
<meta name="author" content="Oliver Ernster">
<meta name="robots" content="index, follow">
<meta name="theme-color" content="{THEME_COLOR}">
<link rel="canonical" href="{SITE_URL}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{APP_NAME}">
<meta property="og:title" content="{APP_NAME}: {SITE_TAGLINE}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:url" content="{SITE_URL}">
<meta property="og:image" content="{image}">
<meta property="og:image:alt" content="{escape(image_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{APP_NAME}: {SITE_TAGLINE}">
<meta name="twitter:description" content="{escape(description)}">
<meta name="twitter:image" content="{image}">
<link rel="icon" type="image/png" href="{ICON_REL}">
<link rel="stylesheet" href="styles.css">
{_structured_data(description)}
</head>"""


def _nav() -> str:
    return f"""<header class="nav">
  <div class="container nav-inner">
    <a class="brand" href="#top">
      <img src="{ICON_REL}" alt="{APP_NAME} icon">{APP_NAME}</a>
    <nav class="nav-links">
      <a href="#who">Who it's for</a>
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
      <p class="lede">The Decision Architecture series, made playable. Model
        any organisation, read its structural health from 0 to 100 and find
        the moves that make it stronger.</p>
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
        succeed or fail by their structure, not by effort. {APP_NAME} turns
        that argument into an engine you operate directly: the decision
        objects, authority worldlines and structural moves from the books,
        scored live by a deterministic model.</p>
      <div class="features">{_feature_html()}</div>
    </div>
  </section>"""


def _play() -> str:
    board_alt = f"The {APP_NAME} board scoring an organisation's structure"
    guide_alt = f"The {APP_NAME} guide planning a stronger org"
    return f"""<section id="play" class="alt">
    <div class="container">
      <div class="eyebrow">Play by play</div>
      <h2 class="section-title">Watch a score climb, move by move</h2>
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
          <figcaption><b>The line.</b> The guide plans the climb move by
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
    version = f"v<!--VERSION-->{__version__}<!--/VERSION-->"
    return f"""<footer>
  <div class="container footer-inner">
    <div>
      <strong>{APP_NAME}</strong>: {SITE_TAGLINE}<br>
      {escape(APP_COPYRIGHT)} · Local-first · GPL-3.0 + LGPL-3.0 · {version}
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
        f"{APP_NAME} is a Decision Architecture sandbox for architects, senior "
        "engineers and CTOs. Model any organisation, score its structural "
        "health from 0 to 100 and find the moves that make it stronger."
    )
    return (
        '<!DOCTYPE html>\n<html lang="en">\n'
        + _head(description)
        + "\n<body>\n"
        + _nav()
        + '\n<main id="top">\n  '
        + _hero()
        + "\n  "
        + _who()
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
