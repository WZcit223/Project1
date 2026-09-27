"""Simulation plugin registry (docs/simulation-api.md §3)."""

from industrial_ai.core.registry import Registry
from industrial_ai.simulation.base import PluginInfo, PluginKind, SimulationPlugin

SimulationRegistry = Registry[SimulationPlugin]


def new_simulation_registry() -> SimulationRegistry:
    """An empty registry keyed by ``(plugin_id, plugin_version)``."""
    return Registry("simulation plugin", key=lambda p: (p.plugin_id, p.plugin_version))


def describe(plugin: SimulationPlugin) -> PluginInfo:
    return PluginInfo(
        plugin_id=plugin.plugin_id,
        plugin_version=plugin.plugin_version,
        kind=plugin.kind,
        description=plugin.description,
        required_inputs=plugin.required_inputs,
        parameter_schema=plugin.parameter_model.model_json_schema(),
    )


def plugins_of_kind(registry: SimulationRegistry, kind: PluginKind) -> list[SimulationPlugin]:
    return [p for p in registry.list() if p.kind is kind]
