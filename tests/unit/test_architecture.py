"""Architecture enforcement tests (docs/architecture.md §2, rules R1 and R2).

R1: the framework package ``industrial_ai`` never imports a scenario pack.
R2: framework layers only import the layers they are allowed to depend on.

Imports are read statically from the source (AST), including imports guarded by
``TYPE_CHECKING`` and relative imports, so a violation is caught even if the code path never runs.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

FRAMEWORK_PACKAGE = "industrial_ai"
FRAMEWORK_ROOT = Path(__file__).resolve().parents[2] / "src" / FRAMEWORK_PACKAGE

# Scenario packs are top-level packages named ``industrial_ai_<pack>`` (ADR-004).
SCENARIO_PACK_PREFIX = f"{FRAMEWORK_PACKAGE}_"

# Allowed framework-internal dependencies per layer (docs/architecture.md §2).
# A layer may always import itself and the package root (which only holds ``__version__``).
ALLOWED_LAYER_DEPENDENCIES: dict[str, frozenset[str]] = {
    "core": frozenset(),
    "foundation": frozenset({"core"}),
    "scenario": frozenset({"core", "foundation"}),
    "synthetic": frozenset({"core", "foundation", "scenario"}),
    "simulation": frozenset({"core", "foundation", "scenario"}),
    "application": frozenset({"core", "foundation", "scenario", "synthetic", "simulation"}),
    "api": frozenset({"core", "application"}),
}


@dataclass(frozen=True)
class Violation:
    module: str
    imported: str
    rule: str

    def __str__(self) -> str:
        return f"{self.module} imports {self.imported} ({self.rule})"


def module_name(path: Path, root: Path = FRAMEWORK_ROOT) -> str:
    """Dotted module name of a source file inside the framework package."""
    parts = list(path.relative_to(root.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported_modules(source: str, module: str, is_package: bool) -> list[str]:
    """Absolute names of all modules imported by ``source`` (relative imports resolved)."""
    names: list[str] = []
    package_parts = module.split(".") if is_package else module.split(".")[:-1]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                anchor = package_parts[: len(package_parts) - (node.level - 1)]
                base = ".".join([*anchor, node.module] if node.module else anchor)
            names.append(base)
            if base == FRAMEWORK_PACKAGE:
                # ``from industrial_ai import simulation`` imports a layer; record it as such.
                names.extend(f"{base}.{alias.name}" for alias in node.names if alias.name != "*")
    return names


def layer_of(module: str) -> str | None:
    """Framework layer of a module (``industrial_ai.<layer>...``); ``None`` for the package root."""
    parts = module.split(".")
    if parts[0] != FRAMEWORK_PACKAGE or len(parts) < 2:
        return None
    return parts[1]


def check_module(source: str, module: str, is_package: bool) -> list[Violation]:
    """Return all R1 / R2 violations of one framework module."""
    violations: list[Violation] = []
    own_layer = layer_of(module)
    for imported in imported_modules(source, module, is_package):
        top_level = imported.split(".")[0]
        if top_level.startswith(SCENARIO_PACK_PREFIX):
            violations.append(Violation(module, imported, "R1: framework imports a scenario pack"))
            continue
        if top_level != FRAMEWORK_PACKAGE or own_layer is None:
            continue
        target_layer = layer_of(imported)
        if target_layer is None or target_layer == own_layer:
            continue
        if target_layer not in ALLOWED_LAYER_DEPENDENCIES:
            continue  # a module attribute of the root package, e.g. ``from industrial_ai import x``
        if target_layer not in ALLOWED_LAYER_DEPENDENCIES.get(own_layer, frozenset()):
            violations.append(
                Violation(
                    module, imported, f"R2: layer '{own_layer}' may not import '{target_layer}'"
                )
            )
    return violations


def framework_sources() -> list[Path]:
    return sorted(FRAMEWORK_ROOT.rglob("*.py"))


def test_every_framework_layer_has_declared_dependencies() -> None:
    layers = {p.name for p in FRAMEWORK_ROOT.iterdir() if (p / "__init__.py").is_file()}
    assert layers == set(ALLOWED_LAYER_DEPENDENCIES), (
        "Framework layers and ALLOWED_LAYER_DEPENDENCIES are out of sync; "
        "update docs/architecture.md §2 and this test together."
    )


def test_framework_respects_dependency_rules() -> None:
    violations = [
        violation
        for path in framework_sources()
        for violation in check_module(
            path.read_text(encoding="utf-8"), module_name(path), path.name == "__init__.py"
        )
    ]
    assert not violations, "Architecture violations:\n" + "\n".join(map(str, violations))


# --- The checker itself must catch violations (guards against a silently passing test). ---


@pytest.mark.parametrize(
    ("source", "module", "rule"),
    [
        ("import industrial_ai_warehouse", "industrial_ai.core.config", "R1"),
        ("from industrial_ai_warehouse.pack import pack", "industrial_ai.application.x", "R1"),
        ("from industrial_ai.api import app", "industrial_ai.foundation.catalog", "R2"),
        ("from industrial_ai import simulation", "industrial_ai.synthetic.engine", "R2"),
        ("from ..application import workflow", "industrial_ai.simulation.engine", "R2"),
        ("from industrial_ai.simulation.engine import run", "industrial_ai.api.routes", "R2"),
        (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n    from industrial_ai.api import app",
            "industrial_ai.core.registry",
            "R2",
        ),
    ],
)
def test_checker_detects_violation(source: str, module: str, rule: str) -> None:
    violations = check_module(source, module, is_package=False)
    assert [v.rule[:2] for v in violations] == [rule]


@pytest.mark.parametrize(
    ("source", "module"),
    [
        ("from industrial_ai.core.errors import IndustrialAIError", "industrial_ai.api.app"),
        ("from ..core import registry", "industrial_ai.synthetic.engine"),
        ("from . import generators", "industrial_ai.synthetic"),
        ("from industrial_ai import __version__", "industrial_ai.api.app"),
        ("import pandas", "industrial_ai.foundation.datasets"),
        ("from industrial_ai.synthetic import engine", "industrial_ai.application.workflow"),
    ],
)
def test_checker_allows_valid_import(source: str, module: str) -> None:
    assert check_module(source, module, is_package=module.count(".") == 1) == []
