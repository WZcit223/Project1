"""Warehouse scenario definitions (scenario-spec §3–4) and their independence from algorithms."""

from industrial_ai_warehouse.generators.demand import SCENARIO_MAPPING
from industrial_ai_warehouse.scenarios import (
    BUILTIN_SCENARIO_IDS,
    DEFINITIONS_DIR,
    WarehouseScenarioParameters,
    builtin_scenarios,
)
from industrial_ai_warehouse.simulation.inventory import SUPPLY_PARAMETERS

from ..test_architecture import imported_modules, module_name

PACKAGE_ROOT = DEFINITIONS_DIR.parents[1]
SCENARIOS_ROOT = DEFINITIONS_DIR.parent

EXPECTED = {
    "baseline": {},
    "high_demand": {"demand_multiplier": 1.3, "seasonality_multiplier": 1.2},
    "demand_shock": {"shock_multiplier": 2.5, "shock_start_day": 28, "shock_duration_days": 14},
    "supply_disruption": {
        "lead_time_delta": 7,
        "disruption_start_day": 28,
        "disruption_duration_days": 42,
        "supply_capacity_factor": 0.5,
    },
}


def test_exactly_the_four_specified_scenarios() -> None:
    registry = builtin_scenarios()
    assert sorted(registry.keys()) == sorted((s, "1.0.0") for s in BUILTIN_SCENARIO_IDS)
    for scenario_id, parameters in EXPECTED.items():
        spec = registry.get(scenario_id)
        assert spec.pack == "warehouse" and spec.title and spec.description
        assert spec.parameters == parameters


def test_parameter_defaults_are_neutral() -> None:
    defaults = WarehouseScenarioParameters()
    assert defaults.demand_multiplier == defaults.seasonality_multiplier == 1.0
    assert defaults.noise_scale == defaults.shock_multiplier == 1.0
    assert defaults.shock_duration_days == 0 and defaults.lead_time_delta == 0
    assert defaults.supply_capacity_factor == 1.0 and defaults.planner_aware is False


def test_every_parameter_is_applied_by_exactly_one_plugin() -> None:
    """Demand parameters go to the demand generator, supply parameters to the inventory model."""
    generator_effects = {
        "level_multiplier",
        "seasonality_multiplier",
        "noise_scale",
        "shock_multiplier",
        "shock_start_day",
        "shock_duration_days",
    }
    renamed = {str(v) for v in SCENARIO_MAPPING.values()}
    demand = (generator_effects - set(SCENARIO_MAPPING)) | renamed
    fields = set(WarehouseScenarioParameters.model_fields)
    assert demand | SUPPLY_PARAMETERS == fields
    assert not demand & SUPPLY_PARAMETERS


def test_scenarios_do_not_import_strategies_or_simulation() -> None:
    forbidden = (
        "industrial_ai_warehouse.strategies",
        "industrial_ai_warehouse.simulation",
        "industrial_ai_warehouse.generators",
        "industrial_ai.simulation",
        "industrial_ai.synthetic",
    )
    for path in SCENARIOS_ROOT.rglob("*.py"):
        module = module_name(path, PACKAGE_ROOT)
        for imported in imported_modules(
            path.read_text(encoding="utf-8"), module, path.name == "__init__.py"
        ):
            assert not imported.startswith(forbidden), f"{module} imports {imported}"


def test_definition_files_are_the_only_source() -> None:
    files = sorted(p.name for p in DEFINITIONS_DIR.iterdir())
    assert files == sorted(f"{s}.yaml" for s in BUILTIN_SCENARIO_IDS)
