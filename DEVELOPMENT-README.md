# Fulcrum development

This is the guide to working on Fulcrum from source: the environment, the
quality gate and the build scripts. For the design see
[ARCHITECTURE.md](ARCHITECTURE.md); for the test suite see [TESTING.md](TESTING.md).

## Environment

Fulcrum targets Python 3.11 or newer and is developed on 3.13.

Windows:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
python main.py
```

Linux and macOS:

```
python3 -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
python main.py
```

`requirements.txt` is the single runtime dependency (PySide6).
`requirements-dev.txt` adds the tooling: pytest with pytest-cov and pytest-qt,
Pillow for the icons and the site images, plus black, flake8 and ruff. It also
includes Nuitka, which the packaged Windows builds (buildexe.py and
buildinstaller.py) use.

## Project layout

```
fulcrum/
  domain/          pure model: org state, moves, scoring, frames, signals, books
  application/     simulator seam, session, org draft, planner, org guide,
                   guide worker pool, plan, glossary
  infrastructure/  JSON serialization, plan export, HTML and SVG renderers
  ui/              PySide6 board, map, editor and dialogs
  shared/          asset discovery and text helpers (no Qt)
installer/         the bespoke Windows installer, a second application layered
                   the same way: logic decides, scripts build the command text,
                   ops acts, lifecycle composes and the Qt modules present
tests/             domain, application, infrastructure, shared, installer,
                   scripts and structural
assets/            book covers and the generated header-button icons
examples/          reference org JSON: a debt ladder, a healthy reference and
                   the calibration cases (examples/calibration)
docs/              the GitHub Pages site (hand-maintained)
main.py            the composition root
```

## Quality gate

Run all four before pushing:

```
pytest
black --check .
flake8 .
ruff check .
```

Run them from the repo root so the installer and the build scripts are read
too; `.flake8` carries the exclusions and `pyproject.toml` mirrors them for
ruff, so the three tools see the same files at the same width.

`pytest` enforces 100% coverage on the gated layers (domain, application,
infrastructure, shared and the installer's pure modules). The structural
tests in `tests/structural` enforce the architectural invariants: domain
purity, inward dependencies, the 400-line module limit across source, tests
and the installer, the installer importing nothing from the `fulcrum`
package, and its pure modules touching no registry, subprocess, environment
or Qt. Adding a feature means placing it in the right layer (the domain stays
pure; the UI talks only to the application) or those tests fail. The detail
is in [TESTING.md](TESTING.md).

## Build scripts

Each build step is a plain script, run with the venv active from the repo root.
The Windows and macOS builds compile with Nuitka (in `requirements-dev.txt`); the
Linux build is a source-based Flatpak. Build for the platform you are on: the
executable and installer on Windows, the Flatpak on Linux and the disk image on
macOS.

### Icons

```
python generate_icons.py
```

Renders the multi-size PNG set and the multi-resolution `fulcrum.ico` from
`fulcrum.png`, used for the window, the taskbar and the packaged executable.
The electric-glow treatment (transparent keying, colour lift, halo) and a
mass-based trim (the art is cropped to the box holding almost all of its
ink, then squared with a thin margin, so the mark fills the taskbar tile)
are part of the script, so the raw master stays untouched and every
emitted icon carries the shipped look.

```
python generate_button_icons.py
```

Draws the header-button icons (the org tree, the pencil, the guide's
climbing arrow and the overview's two view glyphs) deterministically into
`assets/buttons` at the sizes the app loads, one variant per theme (dark
strokes carry a `_light` suffix). Rerunning writes identical files; edit
the script and rerun rather than editing the PNGs.

### Windows executable

```
python buildexe.py
```

Builds a self-contained Windows executable with Nuitka into
`installer/payload/Fulcrum`, so an end user needs no system Python. The icon,
the book covers, the header-button icons, the stepper arrows, the calibration
examples, the `VERSION` file and the licence texts are bundled beside it so
the app's asset discovery finds them. Set
`FULCRUM_DEBUG_CONSOLE=1` for a console-visible diagnostic build.

On a large organisation the guide spawns worker processes (the pool in
`fulcrum/application/org_guide_parallel.py`); `main.py` calls
`multiprocessing.freeze_support()` so those workers behave inside the
packaged executable, where each worker relaunches the executable itself.
Seeing several `fulcrum.exe` processes during guide planning is the pool
at work, not a fault.

### Windows installer

```
python buildinstaller.py
```

Packages the standalone payload into a single-file installer
(`dist-installer/FulcrumSetup.exe`) that extracts to
`%LOCALAPPDATA%\Programs\Fulcrum`, writes the uninstall entry and creates the
desktop and Start Menu shortcuts. Run `buildexe.py` first.

The installer under `installer/` is a second application, layered like one.
`installer_logic.py` decides (where files go, how two versions compare, what
the uninstall registration says, what a shortcut or a deferred delete asks
Windows to do): it is pure, imports nothing beyond the stdlib and is held at
100% coverage by `tests/installer`. `installer_ops.py` acts
(registry, task list, PowerShell, Win32). `installer_lifecycle.py` composes
the two into install, repair and uninstall. `installer_bundle.py` reads the
payload beside the binary; `installer_theme.py`, `installer_widgets.py`
and `installer_window.py` are the Qt surface, outside the coverage gate as the
app's own UI is. `app.py` is the entry point. Every module is inside the
400-line cap, which the structural test now enforces over `installer/` too.
Nothing under `installer/` may import from the `fulcrum` package: the two
binaries are built and released separately.

### Linux Flatpak

```
./build_flatpak.sh
```

Builds Fulcrum as a Flatpak against the `org.freedesktop.Platform//25.08`
runtime, installs it for the current user and writes a distributable
`fulcrum.flatpak` bundle. The PySide6 wheels are pre-downloaded on the host then
installed offline inside the sandbox, so the build needs no network. Needs
`flatpak` and `flatpak-builder` with the freedesktop 25.08 runtime and SDK. Pass
`--no-bundle` to build and install without the distributable bundle.

```
./clean_flatpak.sh
```

Uninstalls the Flatpak for the current user and removes the Flatpak build
artefacts (`fulcrum.flatpak`, the build and repo directories and the generated
manifest). It leaves the Nuitka and macOS outputs untouched, so the build paths
stay independent.

### macOS disk image

```
python builddmg.py
```

Compiles a standalone `Fulcrum.app` with Nuitka and packages it into
`fulcrum.dmg`. Needs macOS with the Xcode command-line tools, Homebrew and
`create-dmg`. Code signing and notarization run when `DEVELOPER_ID_APPLICATION`,
`APPLE_ID` and `APPLE_APP_PASSWORD` are set; otherwise they are skipped. The
`.icns` derives from the glow-treated icon set `generate_icons.py` emits
(`fulcrum_1024.png` downwards), never from the raw `fulcrum.png` master, so
run the icon generator first or the build warns and ships without a custom
icon.

### GitHub Pages site

The site under `docs/` is hand-maintained static HTML, served from the
`main` branch `/docs` folder: `index.html` plus `why.html`, `model.html`,
`tool.html` and `download.html`, sharing one `styles.css`. Edit the pages
directly. There is no generator: the site is authored, not built, so nothing
can overwrite it. Version numbers in the pages sit between `<!--VERSION-->`
delimiters and are stamped from the `VERSION` file (the packaged builds run
this automatically):

```
python stamp_version.py
```

The images under `docs/assets/` are committed alongside the pages: the
play-by-play screenshots in `docs/assets/screenshots/` are captured from the
running app; the book covers in `docs/assets/books/` are web-sized copies
of the masters in `assets/books/`.

### Sensitivity sweep

```
python sensitivity.py
```

Re-scores the ten example archetypes with every scoring coefficient perturbed
by 0.8 and 1.2 (the three composite penalty shares renormalised to keep their
enforced sum) and checks that the published qualitative conclusions still
hold, both canonical blunders staying negative included. Deterministic, no
randomness; exits non-zero if any conclusion fails. The site's model page
(`docs/model.html`) publishes its result.

### Calibration harness

```
python calibrate.py
```

Scores the organisations in `examples/calibration/` against the expected
bands their `calibration` blocks declare, printing the penalty decomposition
beside each verdict and exiting non-zero when any case lands outside its
band. Cases are modelled with outcome knowledge (see the directory's README
and PREREGISTRATION.md: they are permanently ineligible for the blind
validation set); add new ones from `TEMPLATE.json`. The matrixed-enterprise
case is written by `generate_matrixed_enterprise.py` (deterministic and
seeded); change that script and rerun it rather than editing its JSON by
hand.

All three scripts carry smoke tests in `tests/scripts`, so the suite fails if
the sweep loses a conclusion, a calibration case drifts outside its band or
the committed matrixed-enterprise JSON stops matching what the generator
produces. They stay outside the coverage gate: the tests assert they run,
exit zero and emit the shape their reader depends on.

## Conventions

- No magic numbers: domain values come from data, configuration or named
  constants such as those in `SimulationParameters`.
- Frozen dataclasses in the domain; constructor injection only; one composition
  root in `main.py`.
- `black` line length 88; no em dashes anywhere.
- UI sizes go through `ui_scale.px(...)` so the interface scales to the screen.
  Verify UI changes on a real window, not only offscreen.
