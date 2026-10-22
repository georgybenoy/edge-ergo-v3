"""Architectural boundary tests for edge agent modules.

Enforces:
1. `features/` and `scoring/` must NOT import from `camera/` or `overlay/`.
2. No module outside `sync/` may import `requests` or `httpx`.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _get_imports(file_path: Path) -> list[str]:
    """Parses a Python file and returns all imported module names."""
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file_path))
    imported_modules: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.append(node.module)

    return imported_modules


def test_scoring_and_features_boundary() -> None:
    """Verifies scoring and features never import camera or overlay."""
    package_dir = Path(__file__).resolve().parent.parent / "edge_ergo"
    forbidden_targets = {"camera", "overlay", "edge_ergo.camera", "edge_ergo.overlay"}

    isolated_subpackages = ["scoring", "features"]
    violations: list[str] = []

    for subpkg in isolated_subpackages:
        subpkg_path = package_dir / subpkg
        for py_file in subpkg_path.rglob("*.py"):
            imports = _get_imports(py_file)
            for mod in imports:
                if any(
                    mod == target or mod.startswith(f"{target}.") for target in forbidden_targets
                ):
                    violations.append(f"{py_file.name} illegally imports {mod}")

    assert not violations, f"Boundary violation detected: {violations}"


def test_feature_extraction_does_not_know_about_scoring() -> None:
    """Verifies that features subsystem never imports from scoring (Task 5)."""
    package_dir = Path(__file__).resolve().parent.parent / "edge_ergo"
    features_dir = package_dir / "features"
    forbidden_targets = {"scoring", "edge_ergo.scoring"}
    violations: list[str] = []

    for py_file in features_dir.rglob("*.py"):
        imports = _get_imports(py_file)
        for mod in imports:
            if any(mod == target or mod.startswith(f"{target}.") for target in forbidden_targets):
                violations.append(f"{py_file.name} illegally imports scoring module {mod}")

    assert not violations, f"Feature extraction boundary violation: {violations}"


def test_scoring_consumes_features_only() -> None:
    """Verifies that scoring subsystem does not import camera, vision, or overlay."""
    package_dir = Path(__file__).resolve().parent.parent / "edge_ergo"
    scoring_dir = package_dir / "scoring"
    forbidden_targets = {
        "camera",
        "vision",
        "overlay",
        "edge_ergo.camera",
        "edge_ergo.vision",
        "edge_ergo.overlay",
    }
    violations: list[str] = []

    for py_file in scoring_dir.rglob("*.py"):
        imports = _get_imports(py_file)
        for mod in imports:
            if any(mod == target or mod.startswith(f"{target}.") for target in forbidden_targets):
                violations.append(f"{py_file.name} illegally imports {mod}")

    assert not violations, f"Scoring boundary violation: {violations}"


def test_network_client_isolation() -> None:
    """Verifies that only edge_ergo/sync/ can import HTTP clients."""
    package_dir = Path(__file__).resolve().parent.parent / "edge_ergo"
    network_modules = {"requests", "httpx", "urllib.request"}
    violations: list[str] = []

    for py_file in package_dir.rglob("*.py"):
        # Allow sync subpackage to use network clients
        if "sync" in py_file.parts:
            continue

        imports = _get_imports(py_file)
        for mod in imports:
            if any(mod == net or mod.startswith(f"{net}.") for net in network_modules):
                violations.append(f"{py_file.name} illegally imports network module {mod}")

    assert not violations, f"Network client boundary violation: {violations}"
