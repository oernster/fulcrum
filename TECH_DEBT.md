# Fulcrum: Technical Debt

A standing reference to the project's outstanding technical debt. It records what is still open, weighs whether each item is worth doing and gives the rationale. Every item is a behaviour-preserving internal concern: nothing here proposes reverting a feature or changing any UI or UX behaviour. Scope is the whole repository (the `fulcrum` package, the bespoke installer, the delivery scripts and the GitHub Pages site) read against `ARCHITECTURE.md`, `TESTING.md` and the structural tests in `tests/structural/test_architecture.py`.

---

## 1. `ui_scale` holds module-level mutable state

`fulcrum/ui/ui_scale.py` keeps `_state = {"factor": _DEFAULT_FACTOR}` at module scope and mutates it from `init()`, which `main.py` calls once. It is a module-level singleton, and the repo's own rules forbid those; the composition-root whitelist in the structural test does not catch it because the state is a dict rather than a constructed object.

It is small and the contract is honest (the docstring says the composition root sets it once), so the cost of the debt is low: the real price is that scale is global, so nothing can render at two scales and no test can vary the factor without leaking into the next test. Converting it to a `UiScale` value object injected down from `main.py` is the correct shape.

**Blocked on an owner decision.** 52 of the 53 UI modules import `ui_scale`; the UI is outside the coverage gate, so threading an injected value object through them is a wide, behaviour-neutral edit whose only verification is by eye on a real window. The direction is settled; the appetite for that edit (and when to spend it) is not. It stays open until the owner says to spend it.

## 2. The UI layer is 8079 lines with no coverage and some of it is not UI

`.coveragerc` omits `*/ui/*` wholesale, which `TESTING.md` documents as deliberate. For painting, layout and Qt wiring that is correct and matches every other project here.

The open question is how much of those 53 modules is actually presentation. `org_editor.py`, `org_guide_dialog.py` and the board widgets carry sequencing and state-shaping decisions, and each one of those is a decision no test can see. There is no proposal here to test Qt. The item is to keep pulling the decision-shaped parts down into `fulcrum/application` (where `org_draft.py` and `org_guide.py` show the pattern already working) so the omitted surface shrinks toward genuine presentation. This is continuous, not a task with an end state; it is recorded so the omission is never read as "the UI has no logic". The installer's split into a gated `installer_logic.py` and an untested Qt surface is the same move, done in one go, and is the shape to copy.

## 3. The frozen-build worker pool has never been exercised

`org_guide_parallel.py` runs the guide on a `ProcessPoolExecutor`, `main.py` calls `multiprocessing.freeze_support()` before anything else and both pool paths degrade in-process on `BrokenProcessPool`. The code is correct by inspection and the fallback means the worst realistic outcome is a slow guide rather than a broken one.

It has not been run against a real Nuitka standalone build. Under freezing, each worker relaunches the packaged executable, and that is exactly the path no test covers and no developer run exercises.

**Blocked on a packaged build.** This is a verification gap rather than a known defect; nothing in the source can close it: the item closes when someone runs `python buildexe.py` and confirms the packaged binary produces a parallel guide on a large organisation (or falls back cleanly), not when code changes.

## 4. Ruff has never been run against this repository beyond its default rules

`ruff check .` passes clean and exits zero; that is ruff's default selection (E4, E7, E9 and F) doing very little work. Run with `--select ALL` the repository reports **4398 findings**, of which 304 are auto-fixable with `--fix` and a further 829 sit behind `--unsafe-fixes`. The largest families:

| Rule | Count | What it is |
|---|---|---|
| `S101` | 1143 | `assert` (every assertion in the suite; noise, not debt) |
| `ANN001`, `ANN201`, `ANN202` | 1012 | missing type annotations |
| `D1xx`, `D4xx` | ~880 | missing and non-imperative docstrings |
| `COM812` | 269 | missing trailing comma (auto-fixable) |
| `FBT003` | 259 | boolean positional argument in a call |
| `TC001`, `TC002`, `TC003` | 142 | imports that could move under `TYPE_CHECKING` |
| `T201` | 98 | `print` (the analysis and build scripts, by design) |
| `PLR2004` | 87 | magic value in a comparison |

Two findings matter more than the counts. `DTZ` (naive datetime) is **zero**: every timestamp in the repo is timezone-aware, so the correctness risk that family exists to catch is absent. `PLR2004` is the family that touches the repo's own no-magic-numbers rule and is the one worth reading properly.

Clearing this means one dedicated commit per rule family, each with the gate green, never a wholesale `ruff check --fix` across the repository. The `select` list is a ratchet: a family goes into a `[tool.ruff.lint]` config only once it is genuinely clear.

**`RUF100` must not be enabled until the families its noqa comments name are enabled.** It judges `# noqa` against the currently selected rules only, so with a partial `select` it reports five false positives and its fix would delete the `# noqa: F401` in `builddmg.py` (which flake8 does check, so removing it breaks the flake8 gate) and the four `# noqa: BLE001` markers that record deliberate broad handlers in the installer.

`pyproject.toml` carries a `[tool.ruff]` block that mirrors `.flake8` (line length and exclusions) so the two tools read the same files with the same width. It deliberately sets no `select`.

## 5. Two of the four packaging scripts never stamp the version

`buildexe.py` and `buildinstaller.py` both call `stamp_version.main()` before building, so a Windows release cannot ship a GitHub Pages site whose version disagrees with `VERSION`. `builddmg.py` and `build_flatpak.sh` read `VERSION` for their own metadata but never run the stamper.

The exposure is narrow (the stamped surface is the `docs/` site, which is published from `main` rather than from a build) and the failure is cosmetic rather than functional: a release cut on macOS or Linux without a preceding Windows build leaves the site showing the previous version. It is one line in each script. It is recorded rather than fixed because the packaging scripts are the owner's release path and each is verified by running it on its own platform.

---

## Looks like debt, not worth touching

- The ten modules between 351 and 380 lines (`hierarchy.py`, `simulation.py`, `org_draft.py`, `org_guide.py`, `org_guide_dialog.py`, `glossary.py`, `theme.py`, `board_view.py`, `main_window.py` and the installer's `installer_logic.py`) are under the cap and clear of the danger band. They need nothing.
- The `org_guide_*` family (`org_guide.py`, `_compose`, `_growth`, `_parallel`) reads as a file that got split four ways. It is the 400-line cap doing its job and each part is cohesive; merging them would breach the cap immediately.
- The dual GPL-3.0 model and LGPL-3.0 UI split, with three licence files at root plus `INSTALLER_LICENSE`, looks like duplication. It is the deliberate licence design and every file is load-bearing.
- The four `except Exception` blocks in the installer (`installer_ops.py` once, `installer_window.py` three times) each carry a `# noqa: BLE001` and a reason, and each one is a degrade-gracefully path where a raised exception is worse than a status message. Correct as written.
- `docs/model.html` at 409 lines is a hand-written static page, not a module. The LOC cap does not apply to content.

## Not debt (do not "fix" these)

These look like candidates but are correct as they stand; changing them would regress or add cost for nothing.

- **`multiprocessing.freeze_support()` guarded by `if __name__ == "__main__"` in `main.py`.** It looks like boilerplate that could move into the app. It cannot: it has to run before any other import-time work in a frozen worker, and the module guard is what stops a spawned worker starting a second Fulcrum.
- **The `BrokenProcessPool` in-process fallbacks.** They duplicate the chunking loop and look like copy-paste. Each is a different pricing function with different progress semantics, and the duplication is the price of never failing a guide because a worker died.
- **The delivery scripts' length** (`builddmg.py` 424, `buildexe.py` and `buildinstaller.py` 317 each). These are linear recipes read top to bottom and are exempt from the module cap by design. Do not raise length against them. The installer under `installer/` is not one of these: it is a second application and is held to the cap.
- **The coverage omissions of `main.py`, `shared/resources.py`, `application/interfaces.py` and `version.py`.** Composition root, resource path resolution, Protocol declarations and a version reader. Nothing there is a decision, and testing them would test the language.
- **The coverage omissions of the installer's Qt and side-effect modules** (`app.py`, `installer_bundle.py`, `installer_lifecycle.py`, `installer_ops.py`, `installer_theme.py`, `installer_widgets.py`, `installer_window.py`). The decisions were lifted into `installer_logic.py` and the command text it produces into `installer_scripts.py`, both gated at 100%; what remains is widgets, a registry and subprocess edge plus the composition that wires them. Testing `installer_ops.py` would mean writing to the real HKCU hive.
- **`docs/` being hand-maintained with no generator.** The generator that used to write `docs/index.html` was retired because it had diverged: it emitted a single page with no navigation while the live site carries four further hand-written pages. The site is authored, not built. Do not reintroduce a generator without teaching it the whole page set.
- **`VERSION` as the only real version string, with `stamp_version.py` writing the delimited tokens into the `docs/` site.** The apparent duplication is generated, not maintained. No documentation outside the site carries version data.
- **The 45 tracked PNGs.** Every one is emitted by `generate_icons.py` from a single master and consumed by a named packaging path (PE icon, installer badge, hicolor set, `.icns` source). This is the single-master rule working, not asset sprawl.
