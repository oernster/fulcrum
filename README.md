# Fulcrum

Fulcrum turns the Decision Architecture model into a playable engine. You fix a
failing organisation by choosing structural moves (delegate authority, stabilise
interfaces, realign incentives or collapse a boundary) and a deterministic model
scores the result from 0 to 100. You can play generated levels, model your own
organisation or ask for a guide to a stronger structure.

It is a local-first desktop app: everything runs on your machine and nothing
leaves it.

A short tour and the books behind it are at <https://oernster.github.io/fulcrum/>.

## Who it is for

- Software architects, senior engineers and CTOs who want to reason about org
  structure as a system of decisions rather than a headcount chart.
- Readers of the Decision Architecture series who want the model in their hands.
- Anyone curious about why organisations slow down as they scale.

## Who it is not for

- It is not an HR or performance-management tool.
- It is not a project tracker or a roadmap planner.
- It is not a cloud service; there is no account and no server.

## Capabilities

- Generated levels, each resampled until it provably has a great move to find.
- "Model my organisation": a hierarchical editor for domains, sub-domains, teams
  and the dependencies between them, with inline add and remove. A quick wizard
  is also there for a fast first position.
- Per-team headcount that rolls up through the domain hierarchy to a whole-org
  total, so a 100k-person structure is as workable as a handful of teams. It is
  descriptive context and never changes the structural score.
- Two example org sets under `examples/`: a debt ladder that worsens with scale
  and a well-designed reference set that stays healthy.
- Signals to watch (handoff queue age, escalations, rework and influence without
  authority), each carrying its own definition: hover for a gloss, click for the
  full meaning.
- Structural moves scored from blunder to great. A Guide plans a move-by-move
  path from the current org to a stronger one (optionally letting the org grow),
  and you can play a move straight from the guide.
- Take a move back: an undo stack steps the organisation back through the moves
  you have played, from the board or with Ctrl+Z.
- Plan export as a self-contained HTML report or as JSON you can re-import to
  resume the organisation and the moves played on it.
- Full keyboard navigation: the whole interface sits on one explicit focus ring,
  so every control is reachable without a mouse.
- Help built in: a decision glossary and a background page on the Decision
  Architecture books.

## Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ (developed on 3.13) |
| UI | PySide6 (Qt for Python) |
| Persistence | Local JSON files |
| Tests | pytest, 100% gate on domain, application and infrastructure |
| Format and lint | black (line length 88), flake8 |
| Icons and images | Pillow (build time) |
| Packaging | Nuitka (Windows and macOS), Flatpak (Linux) |
| Site | static HTML from `build_docs.py`, served on GitHub Pages |
| Licence | model GPL-3.0, UI LGPL-3.0 |

## Install and run

Windows:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Linux and macOS:

```
python3 -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Documentation

- [Architecture](ARCHITECTURE.md): the layers, the invariants and the model,
  with each invariant linked to the test that enforces it.
- [Development](DEVELOPMENT-README.md): running from source, the quality gate
  and the build scripts (icons, the Windows executable and installer, the Linux
  Flatpak, the macOS disk image and the site).
- [Testing](TESTING.md): how the suite is structured, how to run it and how to
  read its result.

## Test

```
pytest
```

The suite fails below 100% coverage on the gated layers. See [TESTING.md](TESTING.md).

## Build

The development builds for Windows, Linux and macOS (the icon set, the Windows
executable and installer, the Linux Flatpak, the macOS disk image and the GitHub
Pages site) are described in [DEVELOPMENT-README.md](DEVELOPMENT-README.md).

## Licence

Dual-licensed by component: the model under GPL-3.0 and the user interface (the
PySide6 layer) under LGPL-3.0. See [LICENSE](LICENSE) for the split, with the
full texts in [LICENSE-GPL-3.0.txt](LICENSE-GPL-3.0.txt) and
[LICENSE-LGPL-3.0.txt](LICENSE-LGPL-3.0.txt). The running app shows both under
Help.
