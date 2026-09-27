"""Gate 8: the three replenishment strategies are compared on identical demand via engine.compare.

Fixture → M5 adapter → synthetic operations → scenario demand → demand timeline → rolling forecast
(from a warm-up period before the horizon) → inventory simulation × {reorder_point, safety_stock,
dynamic}.
"""

from datetime import timedelta
from pathlib import Path

import pandas as pd
from pydantic import JsonValue

from industrial_ai.foundation.datasets import DatasetBundle
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.simulation import (
    ComparisonResult,
    RunContext,
    SimulationEngine,
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


def compare(scenario: ScenarioSpec | None) -> ComparisonResult:
    retail = M5Adapter().load(FIXTURE)
    start = retail.table("sales").data["date"].max().date() + timedelta(days=1)
    end = start + timedelta(days=HORIZON_DAYS - 1)
    demand = generate_synthetic_demand(
        retail, DemandConfig(start=start, periods=HORIZON_DAYS), SEED, scenario
    )
    hybrid = build_hybrid_bundle(retail, generate_operations(retail, SEED))
    bundle = DatasetBundle(
        hybrid.bundle_id, "1", {**hybrid.tables, "synthetic_demand": demand}, hybrid.source
    )
    sim = engine()
    forecast = sim.run(
        "seasonal_naive",
        build_demand_timeline(retail, demand),
        None,
        {"entity_columns": ["product_id", "store_id"], "forecast_horizon_days": 56},
        RunContext(
            run_id="gate8.forecast",
            seed=SEED,
            start_date=start - timedelta(days=WARM_UP_DAYS),
            end_date=end,
        ),
    )
    context = RunContext(run_id="gate8", seed=SEED, start_date=start, end_date=end)
    variants: dict[str, dict[str, JsonValue]] = {s: {"strategy_id": s} for s in STRATEGIES}
    return sim.compare(
        "inventory_simulation",
        bundle,
        scenario,
        variants,
        context.with_upstream("forecast", forecast),
    )


def test_three_strategies_compared_on_identical_demand() -> None:
    comparison = compare(None)
    ledgers = {name: r.table("inventory_ledger").data for name, r in comparison.variants.items()}
    demand = ledgers["reorder_point"][["date", "product_id", "warehouse_id", "demand"]]
    for ledger in ledgers.values():
        pd.testing.assert_frame_equal(ledger[demand.columns], demand)
        assert (ledger["fulfilled"] + ledger["lost_sales"] == ledger["demand"]).all()

    table = comparison.metrics_table()
    assert list(table.index) == list(STRATEGIES)
    service = {s: comparison.variants[s].metric("fill_rate").value for s in STRATEGIES}
    cost = {s: comparison.variants[s].metric("inventory_cost").value for s in STRATEGIES}
    assert all(v is not None for v in (*service.values(), *cost.values()))
    # Strategies differ (validation.md: non-trivial difference in service level or cost).
    assert len({round(v or 0.0, 3) for v in service.values()}) > 1
    # Safety stock protects service compared with the no-safety-stock reorder point.
    assert (service["safety_stock"] or 0.0) > (service["reorder_point"] or 0.0)


def test_comparison_is_reproducible() -> None:
    first = compare(None).metrics_table()
    second = compare(None).metrics_table()
    pd.testing.assert_frame_equal(first, second)


def test_high_demand_hurts_the_static_strategy_more() -> None:
    high = ScenarioSpec(
        scenario_id="high_demand",
        version="1.0.0",
        pack="warehouse",
        title="High demand",
        parameters={"demand_multiplier": 1.3},
    )
    base, stressed = compare(None), compare(high)

    def drop(strategy: str) -> float:
        before = base.variants[strategy].metric("fill_rate").value
        after = stressed.variants[strategy].metric("fill_rate").value
        assert before is not None and after is not None
        return before - after

    assert drop("reorder_point") > 0  # validation.md: the static strategy responds to scenarios
    assert drop("dynamic") < drop("reorder_point")  # the forecast-driven strategy adapts
