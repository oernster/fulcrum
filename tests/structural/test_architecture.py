"""Structural tests: enforce layer boundaries and module size via AST scan."""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PKG = _ROOT / "fulcrum"
_INSTALLER = _ROOT / "installer"
_MAX_LINES = 400
# The installer's own payload is staged build output, not source.
_INSTALLER_PAYLOAD = "payload"

_DOMAIN_FORBIDDEN = {
    "os",
    "sys",
    "pathlib",
    "time",
    "random",
    "threading",
    "logging",
    "datetime",
    "json",
    "csv",
}
_OUTER_LAYERS = ("fulcrum.application", "fulcrum.infrastructure", "fulcrum.ui")
_FORBIDDEN_FOR_APPLICATION = ("fulcrum.infrastructure", "fulcrum.ui")


def _python_files(directory):
    return sorted(directory.rglob("*.py"))


def _imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.add(node.module.split(".")[0])
    return found


def test_domain_imports_no_io_or_outer_layers():
    for path in _python_files(_PKG / "domain"):
        modules = _imported_modules(path)
        assert not (modules & _DOMAIN_FORBIDDEN), path.name
        assert not any(m.startswith(_OUTER_LAYERS) for m in modules), path.name


def test_application_does_not_import_infrastructure_or_ui():
    for path in _python_files(_PKG / "application"):
        modules = _imported_modules(path)
        assert not any(
            m.startswith(_FORBIDDEN_FOR_APPLICATION) for m in modules
        ), path.name


def _installer_sources():
    return [
        path
        for path in _python_files(_INSTALLER)
        if _INSTALLER_PAYLOAD not in path.parts
    ]


def test_modules_stay_under_the_line_limit():
    # Test modules are held to the same cap as source: an oversized test
    # file hides structure exactly the way an oversized source file does.
    # The installer is a second application, not a build recipe, so it is
    # held to the cap as well.
    paths = list(_python_files(_PKG)) + list(_python_files(_ROOT / "tests"))
    paths += _installer_sources()
    for path in paths:
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert line_count <= _MAX_LINES, f"{path.name}: {line_count}"


def test_the_installer_stays_standalone():
    # The installer is compiled separately and must pull in nothing from the
    # application: an import of fulcrum here would drag the whole package
    # into the setup binary and couple two release artefacts together.
    for path in _installer_sources():
        modules = _imported_modules(path)
        assert not any(m.split(".")[0] == "fulcrum" for m in modules), path.name


def test_the_installer_decisions_touch_no_side_effects():
    # installer_logic is the gated layer: it is testable precisely because
    # it never reaches the registry, a subprocess, the environment or Qt.
    modules = _imported_modules(_INSTALLER / "installer_logic.py")
    forbidden = {"winreg", "subprocess", "os", "sys", "ctypes", "PySide6"}
    assert not (modules & forbidden)
