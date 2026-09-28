"""Warehouse scenario pack: the Golden Path pipeline (docs/architecture.md §5).

reference (M5 format) → canonical retail bundle → synthetic operations → scenario demand →
demand timeline → rolling forecast (with warm-up) → inventory simulation × strategies (compared on
identical demand, supply draws and seed).

Registered with the framework through the ``industrial_ai.scenario_packs`` entry point
(``pack`` below). The framework never imports this module by name.
"""

from datetime import timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from industrial_ai.application import ComponentInfo, PackRunOutput, ResolvedRun, ScenarioPack
from industrial_ai.foundation.datasets import DatasetBundle
from industrial_ai.scenario import ScenarioRegistry
from industrial_ai.simulation import (
    RunContext,
    SimulationEngine,
    SimulationRegistry,
    new_simulation_registry,
)
from industrial_ai.simulation.forecasting import (
    LightGBMForecast,
    MovingAverageForecast,
    SeasonalNaiveForecast,
)
from industrial_ai.simulation.registry import describe
from industrial_ai_warehouse import __version__
from industrial_ai_warehouse.adapters.m5 import M5Adapter
from industrial_ai_warehouse.generators import (
    DemandConfig,
    build_demand_timeline,
    build_hybrid_bundle,
    generate_operations,
    generate_synthetic_demand,
)
from industrial_ai_warehouse.scenarios import builtin_scenarios
from industrial_ai_warehouse.simulation import InventorySimulationPlugin
from industrial_ai_warehouse.strategies import builtin_strategies

ForecastModel = Literal["seasonal_naive", "moving_average", "lightgbm"]
STRATEGY_IDS = ("reorder_point", "safety_stock", "dynamic")


class WarehouseRunOptions(BaseModel):
    """``RunRequest.options`` for the warehouse pack."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    forecast_model: ForecastModel = "seasonal_naive"
    strategies: tuple[str, ...] = STRATEGY_IDS
    warm_up_days: int = Field(default=56, ge=14)
    """Forecast origins start this many days before the horizon (σ_e needs past errors)."""
    forecast_horizon_days: int = Field(default=56, ge=7)

    @field_validator("strategies")
    @classmethod
    def _known(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        registered = {s.strategy_id for s in builtin_strategies().list()}
        unknown = sorted(set(value) - registered)
        if not value or unknown or len(set(value)) != len(value):
            raise ValueError(
                f"strategies must be distinct, non-empty and known; unknown: {unknown}"
            )
        return value


class WarehousePack:
    pack_id = "warehouse"
    pack_version = __version__.split(".dev")[0]
    title = "Inventory Demand Forecasting & Replenishment Simulation"
    description = (
        "Warehouse / inventory validation case: M5 reference demand + synthetic operations; "
        "forecast plugins and replenishment strategies compared under scenarios."
    )
    run_options_model: type[BaseModel] = WarehouseRunOptions
    requires_reference = True
    """``RunRequest.reference``: directory with M5-format files (calendar, sales, prices,
    SOURCE.json)."""

    def scenarios(self) -> ScenarioRegistry:
        return builtin_scenarios()

    def components(self) -> list[ComponentInfo]:
        models = [
            ComponentInfo(
                kind=info.kind.value,
                component_id=info.plugin_id,
                version=info.plugin_version,
                description=info.description,
                parameter_schema=info.parameter_schema,
            )
            for info in map(describe, simulation_registry().list())
        ]
        strategies = [
            ComponentInfo(
                kind="strategy",
                component_id=s.strategy_id,
                version=s.strategy_version,
                description=s.description,
                parameter_schema=s.parameter_model.model_json_schema(),
            )
            for s in builtin_strategies().list()
        ]
        return models + strategies

    def engine(self) -> SimulationEngine:
        return SimulationEngine(simulation_registry())

    def run(self, resolved: ResolvedRun) -> PackRunOutput:
        options = resolved.options
        assert isinstance(options, WarehouseRunOptions)
        request, scenario, seed = resolved.request, resolved.scenario, resolved.request.seed
        assert request.reference is not None  # requires_reference: checked by the runner
        retail = M5Adapter().load(Path(request.reference))
        start = retail.table("sales").data["date"].max().date() + timedelta(days=1)
        end = start + timedelta(days=request.horizon_days - 1)
        operations = generate_operations(retail, seed)
        hybrid = build_hybrid_bundle(retail, operations)
        demand = generate_synthetic_demand(
            retail,
            DemandConfig(start=start, periods=request.horizon_days),
            seed,
            scenario,
            dataset_id=f"{resolved.run_id}.synthetic_demand",
        )
        timeline = build_demand_timeline(retail, demand)
        engine = self.engine()
        forecast = engine.run(
            options.forecast_model,
            timeline,
            None,
            {
                "entity_columns": ["product_id", "store_id"],
                "forecast_horizon_days": options.forecast_horizon_days,
            },
            RunContext(
                run_id=f"{resolved.run_id}.forecast",
                seed=seed,
                start_date=start - timedelta(days=options.warm_up_days),
                end_date=end,
            ),
        )
        bundle = DatasetBundle(
            hybrid.bundle_id, "1", {**hybrid.tables, "synthetic_demand": demand}, hybrid.source
        )
        variants: dict[str, dict[str, JsonValue]] = {
            s: {"strategy_id": s} for s in options.strategies
        }
        comparison = engine.compare(
            "inventory_simulation",
            bundle,
            scenario,
            variants,
            RunContext(
                run_id=resolved.run_id, seed=seed, start_date=start, end_date=end
            ).with_upstream("forecast", forecast),
        )
        inputs = {f"hybrid.{name}": table for name, table in hybrid.tables.items()}
        inputs["synthetic_demand"] = demand
        inputs["demand_timeline"] = timeline
        return PackRunOutput(
            comparison=comparison,
            supporting={"forecast": forecast},
            inputs=inputs,
            labels=("prototype", "synthetic-data"),
        )


def simulation_registry() -> SimulationRegistry:
    """Forecast plugins (framework) and the inventory simulation with the built-in strategies."""
    registry = new_simulation_registry()
    for plugin in (SeasonalNaiveForecast(), MovingAverageForecast(), LightGBMForecast()):
        registry.register(plugin)
    registry.register(InventorySimulationPlugin(builtin_strategies()))
    return registry


pack: ScenarioPack = WarehousePack()
"""The instance exposed through the ``industrial_ai.scenario_packs`` entry point."""
