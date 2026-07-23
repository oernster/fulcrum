# Fulcrum architecture

Fulcrum turns the Decision Architecture model into a deterministic engine and
wraps it in a local-first PySide6 desktop app. The architecture is invariant
first: the rules below are enforced by tests, not by convention.

## Invariants

| Invariant | Enforced by |
|---|---|
| The domain is pure: standard library only, no I/O, no frameworks, no wall-clock reads. | `tests/structural/test_architecture.py::test_domain_imports_no_io_or_outer_layers` |
| Dependencies point inward: the application never imports infrastructure or UI. | `tests/structural/test_architecture.py::test_application_does_not_import_infrastructure_or_ui` |
| No module exceeds 400 lines. | `tests/structural/test_architecture.py::test_modules_stay_under_the_line_limit` |
| The domain, application and infrastructure are covered 100%. | `--cov-fail-under=100` in `pyproject.toml` with `.coveragerc` |
| One explicit composition root. | `main.py` is the only place concrete infrastructure is constructed. |

## Layers

UI to Application to Domain, with Infrastructure pointing in to the same Domain.
A small Shared module holds framework-free helpers.

- **Domain** (`fulcrum/domain`): value objects (`OrgState`, `Team`, `Dependency`, `Domain`), the recursive domain hierarchy and its headcount roll-ups, structural `Move`s, the deterministic scoring model (`evaluate`), the lagging-indicator signals and the reference data for the books. Frozen dataclasses, tuples over lists, validation in `__post_init__`. Pure.
- **Application** (`fulcrum/application`): the `Simulator` Protocol seam and a `DeterministicSimulator`, the `GameSession`, the blueprint intake compiler and its inverse (`org_to_blueprint`, the round-trip editing seam), the editable org draft behind the editor (`org_draft`, `org_draft_nodes`), the shared lead-and-owner name pool, the solvable level generator, the improvement planner (the Guide), the drill-down map model, the plan report builder, the glossary (definitions plus the `short_help` tooltip source) and the book showcase. DTOs cross the boundary.
- **Infrastructure** (`fulcrum/infrastructure`): the shared JSON serialization for org states and moves, the plan repository and exporter (atomic writes), the current-org autosave (`FileOrgStore`, restoring the last session on launch), the HTML and SVG renderers and the system clock. Implements the application Protocols and owns all I/O.
- **UI** (`fulcrum/ui`): PySide6 widgets and dialogs (the board, the navigable org map, the two-pane organisation editor with its tree and inspector panes, the guide, the glossary, the book background and the about/licence dialogs) plus two thin controllers the main window delegates to (`org_intake` for everything that replaces the session, `plan_files` for plan import and export), a client of the application only. A `ui_scale` factor set once at startup keeps the whole interface sized to the screen. This is the only LGPL-3.0 component; the model and the rest of the project are GPL-3.0 (see LICENSE).
- **Shared** (`fulcrum/shared`): runtime asset discovery (icon, licence, book covers and stepper arrows), with no Qt dependency.

## Execution flow

`main.py` builds the services (simulator, plan exporter, clock, org store), injects them into `MainWindow` and starts the Qt loop. On launch the window restores the autosaved org when one exists and generates a fresh one otherwise; every session change and the window close write the current org back through the injected `OrgStore`, which is what lets "Edit my org" reopen the model across restarts. A `GameSession` holds the current `OrgState` and a snapshot stack, so a played move can be taken back; playing a move calls the pure `apply_move`; the board reads score, signals and move valuations from the injected simulator. The editor itself is a pure function of an `OrgBlueprint`: fresh models seed a starter draft and "Edit my org" serialises the live org back to a blueprint, so wizard-built, imported, generated and previously edited orgs are all equally editable.

## The model

Each team has a resolution capacity that falls when it lacks local authority, when it is coupled, when its incentives are skewed and when it grows past a comfortable size. Effective arrivals rise with propagation delay. Three bounded penalties (system backlog, the share of teams without authority and mean incentive skew) compose into a 0..100 score, then a gentle further penalty applies where a team that many others depend on cannot decide locally: the influence-without-authority gap. The watched signals (handoff queue age, escalations, rework and influence without authority) read the same state. A move's value is the score delta, classified from blunder to great. Every coefficient lives in `SimulationParameters`, so there are no hidden constants. Headcount is descriptive only: each team carries a people count that rolls up through the hierarchy to the org total without entering the score.

## Design decisions

| Decision | Rationale |
|---|---|
| Python + PySide6, not Go + React | A visualisation-heavy desktop tool is PySide6 home turf and the compute is bounded. The simulator sits behind a Protocol so a faster kernel stays a reversible, deferred choice. |
| Total-system latency, not accumulated queue | Bounded and stable, so adding a saturated approval gate is robustly harmful rather than a mean-dilution artifact. |
| New effects as gentle multiplicative terms | The cognitive-load and influence-without-authority terms are zero in the benign case, so they never disturb an existing position and only bite where the gap is real. |
| JSON plans, not CSV | Matches the nested shape of an org and the move sequence played on it. |
| Greedy planner | The move set is small, so a greedy best line is explainable and fast, like a chess engine's principal variation. |
| Generated levels resampled until solvable | Every level provably has a great move, the way a puzzle generator verifies a solution before shipping. |

## Tooling

The development builds are plain scripts, not a framework: `generate_icons.py` (the icon set), `buildexe.py` and `buildinstaller.py` (the standalone executable and the Windows installer, via Nuitka) and `build_docs.py` (the GitHub Pages site under `docs/`, rendered from the same book data the app uses). See [DEVELOPMENT-README.md](DEVELOPMENT-README.md).

## Quality

`black` (line length 88) and `flake8` run clean; `pytest` enforces 100% coverage on the gated surface. UI, `main.py`, resource discovery, the application Protocol definitions and the version module are excluded as composition or framework glue. The structural tests enforce the invariants above. See [TESTING.md](TESTING.md).
