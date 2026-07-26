# Fulcrum architecture

Fulcrum turns the Decision Architecture model into a deterministic engine and
wraps it in a local-first PySide6 desktop app. The architecture is invariant
first: the rules below are enforced by tests, not by convention.

## Invariants

| Invariant | Enforced by |
|---|---|
| The domain is pure: standard library only, no I/O, no frameworks, no wall-clock reads. | `tests/structural/test_architecture.py::test_domain_imports_no_io_or_outer_layers` |
| Dependencies point inward: the application never imports infrastructure or UI. | `tests/structural/test_architecture.py::test_application_does_not_import_infrastructure_or_ui` |
| No module exceeds 400 lines, test modules included. | `tests/structural/test_architecture.py::test_modules_stay_under_the_line_limit` |
| The domain, application and infrastructure are covered 100%. | `--cov-fail-under=100` in `pyproject.toml` with `.coveragerc` |
| One explicit composition root. | `main.py` is the only place concrete infrastructure is constructed. |

## Layers

UI to Application to Domain, with Infrastructure pointing in to the same Domain.
A small Shared module holds framework-free helpers.

- **Domain** (`fulcrum/domain`): value objects (`OrgState`, `Team`, `Dependency`, `Domain`, `AuthorityClaim`), the recursive domain hierarchy with its headcount roll-ups and its scoring frames (a focused section, and the top level played as rolled-up root units), structural `Move`s (the vocabulary in `move_base`, the structural handlers in `moves`, the claim moves in `moves_claims`), the deterministic scoring model (`evaluate`, including contested ownership), the lagging-indicator signals with their display formatting and the reference data for the books. A dependency endpoint may be a team or a whole domain; each frame prices the edges whose endpoints both appear as its nodes. A claim's subject is always a team; its claimant may be a team, a unit or an unmodelled label. Frozen dataclasses, tuples over lists, validation in `__post_init__`. Pure.
- **Application** (`fulcrum/application`): the `Simulator` Protocol seam and a `DeterministicSimulator`, the `GameSession` (position, focus frame, history), the off-thread scope analysis, the blueprint intake compiler and its inverse (`org_to_blueprint`, the round-trip editing seam), the editable org draft behind the editor (`org_draft` with its serialisation, conversion and claim mixins and the `org_draft_nodes` vocabulary), the shared lead-and-owner name pool, the solvable level generator, the improvement planner and the whole-hierarchy org guide built on it (a plan for every frame, whose leaf lines compose into an honest whole-org headline), the drill-down map model, the plan report builder, the glossary (definitions plus the `short_help` tooltip source, with the move-classification bands rendered from the engine's own thresholds) and the book showcase. DTOs cross the boundary.
- **Infrastructure** (`fulcrum/infrastructure`): the shared JSON serialization for org states and moves, the plan repository and exporter (atomic writes), the current-org autosave (`FileOrgStore`, restoring the last session on launch), the HTML and SVG renderers and the system clock. Implements the application Protocols and owns all I/O.
- **UI** (`fulcrum/ui`): PySide6 widgets and dialogs (the board with its composed scope presenter, the navigable org map, the two-pane organisation editor with its tree and inspector panes and node-level dependency table, the hierarchy guide (a two-pane tree of every frame's line, computed on a worker thread), the glossary, the book background and the about/licence dialogs) plus two thin controllers the main window delegates to (`org_intake` for everything that replaces the session, `plan_files` for plan import and export), a client of the application only. A `ui_scale` factor set once at startup keeps the whole interface sized to the screen. This is the only LGPL-3.0 component; the model and the rest of the project are GPL-3.0 (see LICENSE).
- **Shared** (`fulcrum/shared`): runtime asset discovery (icon, licence, book covers and stepper arrows) and small pure text helpers (`count_noun`), with no Qt dependency.

## Execution flow

`main.py` builds the services (simulator, plan exporter, clock, org store), injects them into `MainWindow` and starts the Qt loop. On launch the window restores the autosaved org when one exists and generates a fresh one otherwise; every session change and the window close write the current org back through the injected `OrgStore`, which is what lets "Edit my org" reopen the model across restarts. A `GameSession` holds the current `OrgState`, the focus frame and a snapshot stack, so a played move can be taken back; playing a move translates it from the focused frame onto the real teams then calls the pure `apply_move`; the board reads score, signals and move valuations off-thread from the injected simulator. Drilling on the map focuses a section as its own frame; "Play this level" focuses the top level as rolled-up root units, while the unfocused headline score stays the flat team-level truth. The editor itself is a pure function of an `OrgBlueprint`: fresh models seed a starter draft and "Edit my org" serialises the live org back to a blueprint, so wizard-built, imported, generated and previously edited orgs are all equally editable.

## The model

Each team has a resolution capacity that falls when it lacks local authority, when it is coupled, when its incentives are skewed and when it grows past a comfortable size. Effective arrivals rise with propagation delay. Three bounded penalties (system backlog, the share of teams that cannot decide cleanly and mean incentive skew) compose into a 0..100 score, then two gentle further penalties apply: the influence-without-authority gap (a team many others depend on cannot decide locally) and contested ownership. A claim is another actor asserting the right to decide for a team; every decision class already has a structural owner (the team itself, or the line it escalates to), so any standing claim makes its subject contested. Contest is charged three ways, mirroring authority: the team's capacity takes `contested_penalty` (validated to be at most `authority_penalty`, so contest is never cheaper than clean escalation), a contested team counts in the escalation share and the whole score divides by one plus `contested_weight` per standing claim. The watched signals (handoff queue age, escalations, rework, influence without authority and contested ownership) read the same state. A move's value is the score delta, classified from blunder to great against fixed bands; the bands are absolute within each frame, which is why an aggregate scope can honestly offer nothing better than neutral and the board then points the player deeper. Every coefficient lives in `SimulationParameters`, so there are no hidden constants. Headcount is descriptive only: each team carries a people count that rolls up through the hierarchy to the org total without entering the score.

Dependencies follow one projection rule across every view and frame: an edge (authored between teams, between whole units or across levels) maps each endpoint to the node representing it in the current frame. Edges internal to one node vanish, edges crossing the frame boundary drop and a frame prices exactly the edges whose endpoints both stand as its nodes. A unit-level edge therefore counts at the levels where those units are the actors and is never expanded into synthetic team queues.

## Design decisions

| Decision | Rationale |
|---|---|
| Python + PySide6, not Go + React | A visualisation-heavy desktop tool is PySide6 home turf and the compute is bounded. The simulator sits behind a Protocol so a faster kernel stays a reversible, deferred choice. |
| Total-system latency, not accumulated queue | Bounded and stable, so adding a saturated approval gate is robustly harmful rather than a mean-dilution artifact. |
| New effects as gentle multiplicative terms | The cognitive-load and influence-without-authority terms are zero in the benign case, so they never disturb an existing position and only bite where the gap is real. |
| JSON plans, not CSV | Matches the nested shape of an org and the move sequence played on it. |
| Greedy planner | The move set is small, so a greedy best line is explainable and fast, like a chess engine's principal variation. |
| Generated levels resampled until solvable | Every level provably has a great move, the way a puzzle generator verifies a solution before shipping. |
| Frame projection for unit-level dependencies | An edge between units is a fact about the level where those units act. Projecting it into frames where both endpoints are nodes prices it exactly there, without inventing team queues (cartesian expansion would inflate coupling) and without a separate interface object. |
| Classification bands absolute per frame | The same physical move reads larger the deeper the focus, which is the model's move-locality result. Scaling the bands would stamp "great" on negligible summit deltas; instead the bands stay fixed and the board tells the player that value lives deeper. |
| The top level as an explicit frame, not the default | Root units roll into one actor each only when the player asks (Play this level), so dependencies between roots are priced without changing what the headline flat score means. |
| Any standing claim is contest | The first cut counted a team's own authority as its only structural claimant, and the sensitivity sweep falsified it: the matrix-overlay blunder read positive on escalation-heavy archetypes because it barely contested anyone while diluting every penalty share. The structural owner (the team, or the line it escalates to) is always claimant one, so a standing claim always makes two; resolving in favour of a claimant clears the claims outright rather than leaving one standing. |
| Claims follow their subject into leaf frames only | Contest is a fact about a team's decision class, so it projects wherever that team stands as a node; aggregate frames roll teams into synthetic units and carry no claims, consistent with boundary-collapse being team-level only. |
| Contest priced, not simulated | Reconciliation traffic between claimants is not synthesised as dependency edges (that would recreate the cartesian-expansion problem frame projection rejects); the capacity cut, the escalation share and the per-claim divisor carry the cost instead. |
| Stabilise is frame-scoped | A stabilise move carries its frame's node ids and thins only the edges that frame prices; an untargeted move keeps the legacy thin-everything meaning so saved plans replay unchanged. Without the scoping, hierarchy-guide lines would re-apply the global thinning once per leaf. |
| The guide plans every frame; only leaf lines compose | Sibling leaf frames are disjoint, so their lines apply to the real org without collision and the headline is the real flat score after playing them all. Aggregate rows are shown as the view from that altitude and never composed, since their gains overlap the leaf repairs beneath them: the move-locality result, made visible. |
| Growth is a whole-org line, not a frame move | No frame can price a split or an added owner: a leaf frame drops the cross-boundary edges a split relieves and aggregate frames roll teams into synthetic units. With growth allowed, the guide plans one growth-only line against the real organisation from the position after the leaf repairs and appends it as the tree's last composable row, so its org points are growth's honest worth on top of the other lines. |

## Tooling

The development builds are plain scripts, not a framework: `generate_icons.py` (the icon set), `buildexe.py` and `buildinstaller.py` (the standalone executable and the Windows installer, via Nuitka) and `build_docs.py` (the GitHub Pages site under `docs/`, rendered from the same book data the app uses). See [DEVELOPMENT-README.md](DEVELOPMENT-README.md).

## Quality

`black` (line length 88), `flake8` and `ruff check` run clean; `pytest` enforces 100% coverage on the gated surface. UI, `main.py`, resource discovery, the application Protocol definitions and the version module are excluded as composition or framework glue. The structural tests enforce the invariants above, over the tests themselves as well as the source. See [TESTING.md](TESTING.md).
