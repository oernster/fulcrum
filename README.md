# Fulcrum

Fulcrum turns the Decision Architecture model into an engine you operate. You fix a
failing organisation by choosing structural moves (delegate authority, stabilise
interfaces, realign incentives, collapse a boundary or resolve contested
ownership to a single accountable owner) and a deterministic model scores the
result from 0 to 100. You can play generated levels, model your own organisation
or ask for a guide to a stronger structure.

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
- "Model my organisation": a two-pane editor where the org tree you are
  building is always visible as a structure. Start at any tier from the New
  dropdown (a whole company down to a single team), add items inside a unit
  and set what each one is with a Type dropdown (Company, Division,
  Department, Domain, your own label or Team); units nest to any depth with
  teams as the leaves. Rows drag like folders in a file manager: onto a unit
  to move inside, between rows to reorder, Ctrl held to copy, with illegal
  drops refused on the spot. An inspector edits the selected item, the footer
  shows a live people-and-teams rollup and an empty unit carries a warning
  badge on its own row that explains itself on hover. The dialog opens at
  nearly the size of the app window and can be maximised, so a large
  organisation gets a workspace to match. A quick wizard is also there for a
  fast first position.
- Dependencies between any two items: team to team, unit to unit or across
  levels (a division blocked on a single platform team). An edge counts in
  whichever frame shows both its endpoints as nodes: it merges into the
  drilled map's arrows and the aggregate scores while the flat team-level
  score stays honest.
- Matrix and dual-reporting structure, drawn honestly: an authority claim
  records another actor (a team, a unit or an unmodelled label such as a
  chapter lead) asserting the right to decide for a team. A claimed team is
  contested, reads red on the maps, carries its own watched signal and opens
  its own repair moves: resolve the class to a single owner, or downgrade a
  claimant to an explicitly priced consulted dependency. Claims live in the
  editor beside the dependency table and round-trip through JSON.
- Every level of the map is playable, the top level included: "Play this
  level" scores the top-level units as one actor each, so dependencies
  between them are priced, then "Score the whole org" returns to the flat
  view.
- "Edit my org": reopen the current organisation in the same editor at any
  time, whatever its origin (wizard, JSON import, random generation or a
  previous edit), change it and rescore. The current org autosaves, so the
  model survives closing the app.
- Leads and owners are never blank: every group and team gets a plausible name
  from a built-in pool (overtype it in one motion, or roll the dice for
  another), across the editor, the wizard and random generation.
- Per-team headcount that rolls up through the domain hierarchy to a whole-org
  total, so a 100k-person structure is as workable as a handful of teams. It is
  descriptive context and never changes the structural score.
- Two example org sets under `examples/`: a debt ladder that worsens with scale
  and a well-designed reference set that stays healthy.
- Signals to watch (handoff queue age, escalations, rework, influence without
  authority and contested ownership), each carrying its own definition: hover
  for a gloss, click for the full meaning.
- Structural moves scored from blunder to great. The Guide plans every level
  of the organisation at once: a tree of frames where each leaf line is
  priced in whole-org points (the badges sum to the headline), the leaf
  lines compose into an honest whole-org before and after and an aggregate
  row is labelled as the view from that altitude (its gains overlap the leaf
  repairs beneath it). Teams sitting directly inside a unit that also holds
  sub-units get their own row, so every team counts. A toggle lets the org
  grow, priced where the edges live: a whole-org growth line joins the tree
  as its last composable row, frames whose real teams carry the load may
  split them or add owners and a frame growth cannot improve says so. Every
  step shows its before and after score and previews and plays in place.
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
| Tests | pytest, 100% gate on domain, application, infrastructure and shared |
| Format and lint | black (line length 88), flake8, ruff |
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
