"""Load scenario specifications from YAML files (docs/scenario-spec.md §2).

Files are parsed with ``yaml.safe_load`` (data only, no Python objects) and validated as
:class:`ScenarioSpec`. Pack-specific parameter validation happens when the spec is registered in a
:class:`~industrial_ai.scenario.registry.ScenarioRegistry`.
"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from industrial_ai.core.errors import ScenarioValidationError
from industrial_ai.scenario.registry import ScenarioRegistry
from industrial_ai.scenario.spec import ScenarioSpec

SUFFIXES = (".yaml", ".yml")


def load_scenario(path: Path) -> ScenarioSpec:
    """Parse and validate one scenario file."""
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ScenarioValidationError(f"{path}: not valid YAML: {exc}") from exc
    if not isinstance(content, dict):
        raise ScenarioValidationError(f"{path}: expected a mapping at the top level")
    try:
        return ScenarioSpec.model_validate(content)
    except ValidationError as exc:
        raise ScenarioValidationError(f"{path}: invalid scenario specification: {exc}") from exc


def load_scenarios(directory: Path) -> list[ScenarioSpec]:
    """All scenario files in ``directory`` (not recursive), ordered by file name."""
    if not directory.is_dir():
        raise ScenarioValidationError(f"scenario directory {directory} does not exist")
    files = sorted(p for p in directory.iterdir() if p.suffix in SUFFIXES and p.is_file())
    return [load_scenario(p) for p in files]


def register_directory(registry: ScenarioRegistry, directory: Path) -> list[ScenarioSpec]:
    """Load every scenario file in ``directory`` into ``registry``; returns the registered specs."""
    specs = load_scenarios(directory)
    for spec in specs:
        registry.register(spec)
    return specs
