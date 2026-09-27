"""Warehouse scenarios: parameter model and the four v0.1 scenario definitions (YAML).

Scenarios are configuration only (Scenario ≠ Algorithm): this package does not import strategies
or simulation code, so any scenario can be combined with any compatible strategy.
"""

from pathlib import Path

from industrial_ai.scenario import ScenarioRegistry, register_directory
from industrial_ai_warehouse.scenarios.parameters import WarehouseScenarioParameters

PACK = "warehouse"
DEFINITIONS_DIR = Path(__file__).parent / "definitions"
BUILTIN_SCENARIO_IDS = ("baseline", "high_demand", "demand_shock", "supply_disruption")


def new_scenario_registry() -> ScenarioRegistry:
    """Empty registry that validates against :class:`WarehouseScenarioParameters`."""
    return ScenarioRegistry(PACK, WarehouseScenarioParameters)


def builtin_scenarios() -> ScenarioRegistry:
    """Registry with the four v0.1 scenarios loaded from ``definitions/*.yaml``."""
    registry = new_scenario_registry()
    register_directory(registry, DEFINITIONS_DIR)
    return registry


__all__ = [
    "BUILTIN_SCENARIO_IDS",
    "DEFINITIONS_DIR",
    "PACK",
    "WarehouseScenarioParameters",
    "builtin_scenarios",
    "new_scenario_registry",
]
