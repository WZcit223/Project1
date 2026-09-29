"""Simulation / intelligence layer: plugin protocol, result model, registry and engine."""

from industrial_ai.simulation.base import (
    Metric,
    OutputTable,
    PluginInfo,
    PluginKind,
    PluginOutput,
    RunContext,
    RunMetadata,
    ScenarioResult,
    SimulationPlugin,
    SimulationResult,
)
from industrial_ai.simulation.engine import ComparisonResult, SimulationEngine
from industrial_ai.simulation.registry import (
    SimulationRegistry,
    describe,
    new_simulation_registry,
    plugins_of_kind,
)

__all__ = [
    "ComparisonResult",
    "Metric",
    "OutputTable",
    "PluginInfo",
    "PluginKind",
    "PluginOutput",
    "RunContext",
    "RunMetadata",
    "ScenarioResult",
    "SimulationEngine",
    "SimulationPlugin",
    "SimulationRegistry",
    "SimulationResult",
    "describe",
    "new_simulation_registry",
    "plugins_of_kind",
]
