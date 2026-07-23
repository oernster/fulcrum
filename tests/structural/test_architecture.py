"""Structural tests: enforce layer boundaries and module size via AST scan."""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PKG = _ROOT / "fulcrum"
_MAX_LINES = 400

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


def test_modules_stay_under_the_line_limit():
    # Test modules are held to the same cap as source: an oversized test
    # file hides structure exactly the way an oversized source file does.
    for directory in (_PKG, _ROOT / "tests"):
        for path in _python_files(directory):
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            assert line_count <= _MAX_LINES, f"{path.name}: {line_count}"
