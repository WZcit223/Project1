"""Scenario pack protocol and discovery (docs/plugin-spec.md §3).

A scenario pack is a separate package exposing a :class:`ScenarioPack`. The framework never imports
a pack by name: packs are found through the entry point group ``industrial_ai.scenario_packs`` or
registered explicitly (tests).
"""

from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from industrial_ai.application.models import ResolvedRun
from industrial_ai.core.errors import RegistryError
from industrial_ai.core.registry import Registry
from industrial_ai.foundation.datasets import Dataset
from industrial_ai.scenario import ScenarioRegistry
from industrial_ai.simulation import ComparisonResult, SimulationResult

ENTRY_POINT_GROUP = "industrial_ai.scenario_packs"


@dataclass(frozen=True)
class PackRunOutput:
    """What a pack returns from one run; the runner persists it."""

    comparison: ComparisonResult
    """The compared variants (e.g. strategies) on identical data, scenario and seed."""
    supporting: dict[str, SimulationResult] = field(default_factory=dict)
    """Upstream runs the comparison used (e.g. ``forecast``)."""
    inputs: dict[str, Dataset] = field(default_factory=dict)
    """Datasets the run generated or loaded (reference, synthetic, derived)."""
    labels: tuple[str, ...] = ()


@runtime_checkable
class ScenarioPack(Protocol):
    pack_id: str
    pack_version: str
    title: str
    description: str
    run_options_model: type[BaseModel]
    """Validates ``RunRequest.options``."""

    def scenarios(self) -> ScenarioRegistry:
        """The pack's registered scenarios (validated against its parameter model)."""
        ...

    def run(self, resolved: ResolvedRun) -> PackRunOutput:
        """Execute the pack's pipeline for one validated request; raise on failure."""
        ...


PackRegistry = Registry[ScenarioPack]


def new_pack_registry() -> PackRegistry:
    return Registry("scenario pack", key=lambda p: (p.pack_id, p.pack_version))


def discover_packs() -> PackRegistry:
    """Registry of every pack installed under the ``industrial_ai.scenario_packs`` entry point."""
    registry = new_pack_registry()
    for entry in entry_points(group=ENTRY_POINT_GROUP):
        pack = entry.load()
        if not isinstance(pack, ScenarioPack):
            raise RegistryError(f"entry point {entry.name!r} does not provide a ScenarioPack")
        registry.register(pack)
    return registry
