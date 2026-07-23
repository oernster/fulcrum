# Fulcrum testing

The suite is `pytest` with a hard 100% coverage gate on the layers that carry
logic. For the design see [ARCHITECTURE.md](ARCHITECTURE.md); for the wider
workflow see [DEVELOPMENT-README.md](DEVELOPMENT-README.md).

## Running

From the repo root with the venv active:

```
pytest
```

The configuration in `pyproject.toml` runs coverage automatically and fails the
run below 100% on the gated layers. To format and lint as well:

```
black --check fulcrum tests
flake8 fulcrum tests
ruff check .
```

## Reading the result

Trust the exit code, not the text. Because coverage runs with
`--cov-fail-under=100`, a passing run prints the coverage table last and emits
no "N passed" summary line, so a glance at the tail shows coverage rows rather
than a result. Exit code 0 means every test passed and the coverage gate was
met; a non-zero code means something failed, with the failures printed above the
coverage table. For a plain count, run `pytest --no-cov -q`.

## Layout

The tests mirror the package, one area per layer:

| Area | Kind | I/O |
|---|---|---|
| `tests/domain` | pure unit tests of the model, moves, signals and books | none |
| `tests/application` | unit tests over the Protocol seams, using hand-written fakes | none |
| `tests/infrastructure` | integration tests against real files in a temp directory | temp files |
| `tests/structural` | an AST scan that enforces the architectural invariants | reads source |

## Coverage scope

`.coveragerc` gates the domain, the application, the infrastructure and the
shared text helpers at 100%. It omits the surfaces that are composition or
framework glue: the UI, `main.py`, the shared asset discovery, the application
Protocol definitions, the version module and `generate_icons.py`. Those carry
no branching logic, so they are verified by running the app rather than by the
gate.

## Structural invariants

`tests/structural/test_architecture.py` is part of the suite, not a separate
check. It fails the build if the domain imports I/O or an outer layer; if the
application imports infrastructure or the UI; or if any module exceeds 400
lines, the test modules included (an oversized test file hides structure the
same way an oversized source file does). The architectural rules are
therefore tested, not merely documented.

## Verifying the UI

The UI is outside the coverage gate, so it is checked two ways: by constructing
widgets headlessly (an offscreen `QApplication`) and asserting their structure
and behaviour, then by eye on a real window. Two caveats are worth knowing: a
`QSpinBox` paints its stepper arrows only in a genuinely shown window, so
spinbox styling is verified with a real `show()` rather than an offscreen grab;
and the offscreen platform resolves no real fonts (every glyph renders as a
placeholder box), so anything that measures rendered glyph geometry must run on
the native platform, grabbing widgets without ever showing a window.
