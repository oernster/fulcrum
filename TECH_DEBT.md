# Fulcrum: Technical Debt

A standing reference to the project's outstanding technical debt. It records what is still open, weighs whether each item is worth doing and gives the rationale. Every item is a behaviour-preserving internal concern: nothing here proposes reverting a feature or changing any UI or UX behaviour. Scope is the whole repository (the `fulcrum` package, the bespoke installer, the delivery scripts and the GitHub Pages site) read against `ARCHITECTURE.md`, `TESTING.md` and the structural tests in `tests/structural/test_architecture.py`.

---

## 1. `build_docs.py` and `docs/` have diverged, and regenerating loses the site

`build_docs.py` writes `docs/index.html` and its docstring states that the site "cannot drift from the app". It has drifted. The generator emits a single page with no navigation; the live `docs/index.html` carries fourteen links to `why.html`, `model.html`, `tool.html` and `download.html`, four hand-maintained pages the generator has no knowledge of. Running `python build_docs.py` today would overwrite the published index with a version that strips the entire site navigation and orphans four pages.

This is the highest-value item in the file, because the failure mode is silent and destructive: the script looks safe to run, is documented as the authoritative source and is not. Two ways out:

- Teach `build_docs.py` about the full page set so the claim in its docstring becomes true again, and keep the generated-from-app books section as its reason to exist.
- Or retire the generator, promote `docs/` to hand-maintained in full and delete the docstring's authority claim.

Either resolves it. Leaving both the generator and the hand-edits in place does not, because the next person to read the docstring reaches for the script.

## 2. `installer/app.py` sits outside every gate the rest of the repo is held to

At 1575 lines it is 3.9 times the 400-line module cap, and it is invisible to both enforcement mechanisms:

- The structural LOC test scopes itself to `_PKG = _ROOT / "fulcrum"`, so `installer/` is never measured.
- `.coveragerc` sets `source = fulcrum`, so the installer contributes nothing to the 100% gate and has no tests at all.

The delivery-script exemption covers linear build recipes such as `buildexe.py` and `buildinstaller.py`. It does not cover this file: the installer is a PySide6 application with real logic (payload extraction, HKCU uninstall-key registration, shortcut creation, self-copy for the registered uninstaller, launcher-path resolution through `NUITKA_ONEFILE_BINARY`), and a defect in any of those lands on a user's machine before the app ever starts. It is a second application wearing a build script's exemption.

The proportionate fix is to lift the non-UI logic (registry writes, path resolution, extraction, shortcut targets) into a small testable module under `installer/`, bring that module into the coverage source and leave the Qt widget code as the untested UI surface the rest of the app already treats it as. Extending the structural LOC test over `installer/` follows from that split rather than preceding it.

## 3. `ui_scale` holds module-level mutable state

`fulcrum/ui/ui_scale.py` keeps `_state = {"factor": _DEFAULT_FACTOR}` at module scope and mutates it from `init()`, which `main.py` calls once. It is a module-level singleton, and the repo's own rules forbid those; the composition-root whitelist in the structural test does not catch it because the state is a dict rather than a constructed object.

It is small and the contract is honest (the docstring says the composition root sets it once), so the cost of the debt is low: the real price is that scale is global, so nothing can render at two scales and no test can vary the factor without leaking into the next test. Converting it to a `UiScale` value object injected down from `main.py` is the correct shape. It is a wide, mechanical edit across 53 UI modules, which is why it has not happened, not because the current form is right.

## 4. The UI layer is 8073 lines with no coverage and some of it is not UI

`.coveragerc` omits `*/ui/*` wholesale, which `TESTING.md` documents as deliberate. For painting, layout and Qt wiring that is correct and matches every other project here.

The open question is how much of those 53 modules is actually presentation. `org_editor.py`, `org_guide_dialog.py` and the board widgets carry sequencing and state-shaping decisions, and each one of those is a decision no test can see. There is no proposal here to test Qt. The item is to keep pulling the decision-shaped parts down into `fulcrum/application` (where `org_draft.py` and `org_guide.py` show the pattern already working) so the omitted surface shrinks toward genuine presentation. This is continuous, not a task with an end state; it is recorded so the omission is never read as "the UI has no logic".

## 5. The frozen-build worker pool has never been exercised

`org_guide_parallel.py` runs the guide on a `ProcessPoolExecutor`, `main.py` calls `multiprocessing.freeze_support()` before anything else and both pool paths degrade in-process on `BrokenProcessPool`. The code is correct by inspection and the fallback means the worst realistic outcome is a slow guide rather than a broken one.

It has not been run against a real Nuitka standalone build. Under freezing, each worker relaunches the packaged executable, and that is exactly the path no test covers and no developer run exercises. This is a verification gap, not a known defect: the item closes when a packaged build is confirmed to produce a parallel guide (or to fall back cleanly), not when code changes.

## 6. The analysis scripts at repo root are ungated

`calibrate.py`, `sensitivity.py` and `generate_matrixed_enterprise.py` import the application layer, print results and are covered by nothing. `generate_matrixed_enterprise.py` also sits at 391 lines, inside the 381 to 399 danger band, so the next edit pushes it over the cap.

They are development instruments rather than shipped surface, which is why they are outside the gate. The exposure is that `calibrate.py` is the tool that says whether the scoring model still lands its calibration cases inside their expected bands: a silently broken calibrator reports success. Giving these three a thin smoke test each (runs, exits zero, emits the expected shape) is cheap and buys the confidence the gate otherwise provides. `generate_matrixed_enterprise.py` should drop to 350 or below when it is next touched, whichever way its exemption is read.

---

## Looks like debt, not worth touching

- The seven modules between 351 and 380 lines (`hierarchy.py`, `simulation.py`, `org_draft.py`, `org_guide.py`, `org_guide_dialog.py`, `glossary.py`, `theme.py`) are under the cap and clear of the danger band. They need nothing.
- The `org_guide_*` family (`org_guide.py`, `_compose`, `_growth`, `_parallel`) reads as a file that got split four ways. It is the 400-line cap doing its job and each part is cohesive; merging them would breach the cap immediately.
- The dual GPL-3.0 model and LGPL-3.0 UI split, with three licence files at root plus `INSTALLER_LICENSE`, looks like duplication. It is the deliberate licence design and every file is load-bearing.
- The four `except Exception` blocks in `installer/app.py` each carry a `# noqa: BLE001` and a reason, and each one is a degrade-gracefully path in an installer where a raised exception is worse than a status message. Correct as written.
- `docs/model.html` at 409 lines is a hand-written static page, not a module. The LOC cap does not apply to content.

## Not debt (do not "fix" these)

These look like candidates but are correct as they stand; changing them would regress or add cost for nothing.

- **`multiprocessing.freeze_support()` guarded by `if __name__ == "__main__"` in `main.py`.** It looks like boilerplate that could move into the app. It cannot: it has to run before any other import-time work in a frozen worker, and the module guard is what stops a spawned worker starting a second Fulcrum.
- **The `BrokenProcessPool` in-process fallbacks.** They duplicate the chunking loop and look like copy-paste. Each is a different pricing function with different progress semantics, and the duplication is the price of never failing a guide because a worker died.
- **The delivery scripts' length** (`build_docs.py` 427, `builddmg.py` 426, `buildexe.py`, `buildinstaller.py`). These are linear recipes read top to bottom and are exempt from the module cap by design. Do not raise length against them. Item 1 above is about `build_docs.py`'s correctness, not its size.
- **The coverage omissions of `main.py`, `shared/resources.py`, `application/interfaces.py` and `version.py`.** Composition root, resource path resolution, Protocol declarations and a version reader. Nothing there is a decision, and testing them would test the language.
- **`VERSION` as the only real version string, with `stamp_version.py` writing the delimited tokens into the markdown and `docs/`.** The apparent duplication across files is generated, not maintained.
- **The 45 tracked PNGs.** Every one is emitted by `generate_icons.py` from a single master and consumed by a named packaging path (PE icon, installer badge, hicolor set, `.icns` source). This is the single-master rule working, not asset sprawl.
