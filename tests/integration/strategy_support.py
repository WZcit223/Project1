"""Shared strategy-test pipeline: hybrid environment → demand → forecast → inventory compare."""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from pydantic import JsonValue

from industrial_ai.foundation.datasets import Dataset, DatasetBundle
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.simulation import (
    ComparisonResult,
    RunContext,
    SimulationEngine,
    SimulationResult,
    new_simulation_registry,
)
from industrial_ai.simulation.forecasting import SeasonalNaiveForecast
from industrial_ai_warehouse.adapters.m5 import M5Adapter
from industrial_ai_warehouse.generators import (
    DemandConfig,
    build_demand_timeline,
    build_hybrid_bundle,
    generate_operations,
    generate_synthetic_demand,
)
from industrial_ai_warehouse.simulation import InventorySimulationPlugin
from industrial_ai_warehouse.strategies import builtin_strategies

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "m5_like"
SEED = 20260927
HORIZON_DAYS = 84
WARM_UP_DAYS = 56
STRATEGIES = ("reorder_point", "safety_stock", "dynamic")


def engine() -> SimulationEngine:
    registry = new_simulation_registry()
    registry.register(SeasonalNaiveForecast())
    registry.register(InventorySimulationPlugin(builtin_strategies()))
    return SimulationEngine(registry)


@dataclass(frozen=True)
class Environment:
    retail: DatasetBundle
    hybrid: DatasetBundle
    start: date
    end: date


def environment() -> Environment:
    retail = M5Adapter().load(FIXTURE)
    start = retail.table("sales").data["date"].max().date() + timedelta(days=1)
    hybrid = build_hybrid_bundle(retail, generate_operations(retail, SEED))
    return Environment(retail, hybrid, start, start + timedelta(days=HORIZON_DAYS - 1))


def demand(env: Environment, scenario: ScenarioSpec | None) -> Dataset:
    return generate_synthetic_demand(
        env.retail, DemandConfig(start=env.start, periods=HORIZON_DAYS), SEED, scenario
    )


def run_strategies(
    env: Environment, horizon_demand: Dataset, scenario: ScenarioSpec | None
) -> tuple[SimulationResult, ComparisonResult]:
    """Forecast (with warm-up) on the demand timeline, then compare the three strategies."""
    sim = engine()
    forecast = sim.run(
        "seasonal_naive",
        build_demand_timeline(env.retail, horizon_demand),
        None,
        {"entity_columns": ["product_id", "store_id"], "forecast_horizon_days": 56},
        RunContext(
            run_id="strategies.forecast",
            seed=SEED,
            start_date=env.start - timedelta(days=WARM_UP_DAYS),
            end_date=env.end,
        ),
    )
    bundle = DatasetBundle(
        env.hybrid.bundle_id,
        "1",
        {**env.hybrid.tables, "synthetic_demand": horizon_demand},
        env.hybrid.source,
    )
    context = RunContext(run_id="strategies", seed=SEED, start_date=env.start, end_date=env.end)
    variants: dict[str, dict[str, JsonValue]] = {s: {"strategy_id": s} for s in STRATEGIES}
    comparison = sim.compare(
        "inventory_simulation",
        bundle,
        scenario,
        variants,
        context.with_upstream("forecast", forecast),
    )
    return forecast, comparison
