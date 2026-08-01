# Fulcrum

Fulcrum turns the Decision Architecture model into an engine you operate. You fix a
failing organisation by choosing structural moves (delegate authority, stabilise
interfaces, realign incentives, collapse a boundary or resolve contested
ownership to a single accountable owner) and a deterministic model scores the
result from 0 to 100. You can play generated levels, model your own organisation
or ask for a guide to a stronger structure.

It is a local-first desktop app: everything runs on your machine and nothing
leaves it.

A short tour and the books behind it are at <https://ernster.dev/fulcrum/>.

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
  organisation gets a workspace to match.
- Dependencies between any two items: team to team, unit to unit or across
  levels (a division blocked on a single platform team). An edge counts in
  whichever frame shows both its endpoints as nodes: it merges into the
  drilled map's arrows and the aggregate scores while the flat team-level
  score stays honest.
- Matrix and dual-reporting structure, drawn honestly: an authority claim
  records another actor (a team, a unit or an unmodelled label such as a
  chapter lead) asserting the right to decide for a team. A claimed team is
  contested, reads violet on the maps, carries its own watched signal and opens
  its own repair moves: resolve the class to a single owner, or downgrade a
  claimant to an explicitly priced consulted dependency. Claims live in the
  editor beside the dependency table and round-trip through JSON.
- The board opens as the complete picture: every domain and team at once,
  with a click on any domain drilling straight into that section on the
  navigable map and a synthetic dashed Shell tier grouping a multi-company
  top level without asserting a modelled roof. Hovering a section rings it
  in green to show a click opens it. Every level of the map is
  playable, the top level included: "Play this level" scores the top-level
  units as one actor each, so dependencies between them are priced, then
  "Score the whole org" returns to the complete picture.
- Both maps zoom: corner + and - chips (or the + and - keys on the focused
  map) step the view larger and smaller, with each drill level opening at
  its own fit and zooming over it, so a wide level's small type is one
  press from readable.
- A live move record behind the central header button: every move to date,
  earlier runs marked, each showing the organisation before and after it;
  the record survives restarts and rides along in JSON export and import.
- "Edit my org": reopen the current organisation in the same editor at any
  time, whatever its origin (hand-modelled, JSON import, random generation or a
  previous edit), change it and rescore. The current org autosaves, so the
  model survives closing the app.
- Leads and owners are never blank: every group and team gets a plausible name
  from a built-in pool (overtype it in one motion, or roll the dice for
  another), across the editor and random generation.
- Per-team headcount that rolls up through the domain hierarchy to a whole-org
  total, so a 100k-person structure is as workable as a handful of teams. The
  rolled-up population sets the scale at which each frame prices concentrated
  authority (the prince band: forgiven up to the Dunbar horizon of 150 people,
  priced progressively harder beyond 200); nothing else in the score reads it.
- Three example org sets under `examples/`: a debt ladder that worsens with
  scale, a well-designed reference set that stays healthy and a calibration
  set (`examples/calibration/`, scored by `python calibrate.py`) whose cases
  carry expected score bands drawn from known outcomes, so the coefficients
  answer to lived experience rather than taste. Every calibration case is a
  drillable hierarchy of small varied teams; the six-thousand-person
  enterprise case is generated deterministically by
  `generate_matrixed_enterprise.py`. The calibration cases are also
  available in-app via Organisation | Open example organisation, each loading
  onto the board ready to inspect, play and rework in the editor.
- Signals to watch (handoff queue age, escalations, rework, influence without
  authority, contested ownership, centre escalation load and unowned
  interfaces), each carrying its own definition: hover for a gloss, click for
  the full meaning.
- Structural moves scored from blunder to great. The Guide plans every level
  of the organisation at once: a tree of frames where each leaf line is
  priced in whole-org points (the composing badges sum to the headline and
  a line that would cost the whole organisation is kept out of it, flagged
  with its cost), the leaf
  lines compose into an honest whole-org before and after and an aggregate
  row is labelled as the view from that altitude (its gains overlap the leaf
  repairs beneath it). Teams sitting directly inside a unit that also holds
  sub-units get their own row, so every team counts. A toggle lets the org
  grow, priced where the edges live: a whole-org growth line joins the tree
  as its last composable row, frames whose real teams carry the load may
  split them or add owners and a frame growth cannot improve says so. Every
  step shows its before and after score and previews and plays in place.
- Guide planning that uses the whole machine: on a large organisation the
  heavy pricing spreads across every processor core, with one core left to
  keep the interface painting, so an enterprise of thousands plans in
  seconds rather than minutes. The parallel build is deterministic and
  identical to the single-core one down to the last digit; small
  organisations plan in-process because they finish faster than worker
  processes take to start. Every planning bar (opening the guide, the
  grow toggle, the replan after playing a guide move) carries a Cancel
  button that stops the build within a fraction of a second, so a
  machine without the cores for the pool is never trapped in a long
  serial build.
- Move history that survives closing the app: the session autosaves the
  starting org and every move, the next launch restores it by replay and
  Take a move back steps through earlier runs' moves too, from the board or
  with Ctrl+Z, all the way to the original organisation.
- Plan export as a self-contained HTML report written straight to your
  Downloads folder, covering the whole record with earlier runs visually
  separated from the current one, or as JSON you can re-import to resume
  the organisation and the moves played on it.
- Full keyboard navigation: the whole interface sits on one explicit focus ring,
  so every control is reachable without a mouse.
- Light and dark themes, switched from the header's sun/moon toggle and
  remembered between runs; the whole interface follows, the organisation
  map included, with the authority colours re-weighted per theme so green,
  amber and violet keep their meaning on either surface (violet marks
  contested ownership rather than red, so it stays distinct from the green
  hover ring under red-green colour blindness).
- Help built in: About, both licence texts, a decision glossary and a
  background page on the Decision Architecture books. Long help content
  reads itself down gently, holds at the end and rewinds; it yields the
  moment you scroll by hand and resumes where you stopped.

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
| Site | hand-maintained static HTML under `docs/`, served on GitHub Pages |
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
