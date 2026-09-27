"""Gate 7: the inventory simulation runs on the hybrid environment built from M5-shaped data.

Fixture → M5 adapter → synthetic operations → scenario demand for the horizon → inventory simulation
(test order-up-to strategy until Phase 9 adds the real strategies).
"""

from datetime import timedelta
from pathlib import Path

from industrial_ai.foundation.datasets import DatasetBundle
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.simulation import RunContext
from industrial_ai_warehouse.adapters.m5 import M5Adapter
from industrial_ai_warehouse.generators import (
    DemandConfig,
    build_hybrid_bundle,
    generate_operations,
    generate_synthetic_demand,
)

from ..unit.warehouse.inventory_support import engine

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "m5_like"
SEED = 20260927


def run(scenario: ScenarioSpec | None, level: int) -> tuple[DatasetBundle, float, float]:
    retail = M5Adapter().load(FIXTURE)
    start = retail.table("sales").data["date"].max().date() + timedelta(days=1)
    horizon = DemandConfig(start=start, periods=56)
    demand = generate_synthetic_demand(retail, horizon, SEED, scenario)
    ops = generate_operations(retail, SEED)
    hybrid = build_hybrid_bundle(retail, ops)
    bundle = DatasetBundle(
        hybrid.bundle_id, "1", {**hybrid.tables, "synthetic_demand": demand}, hybrid.source
    )
    context = RunContext(
        run_id="gate7", seed=SEED, start_date=start, end_date=start + timedelta(days=55)
    )
    result = engine().run(
        "inventory_simulation",
        bundle,
        scenario,
        {"strategy_id": "test_order_up_to", "strategy_parameters": {"level": level}},
        context,
    )
    ledger = result.table("inventory_ledger").data
    assert len(ledger) == 56 * len(ops.table("initial_inventory").data)
    assert (ledger["fulfilled"] + ledger["lost_sales"] == ledger["demand"]).all()
    service = result.metric("service_level").value
    cost = result.metric("inventory_cost").value
    assert service is not None and cost is not None
    return bundle, service, cost


def test_inventory_simulation_on_hybrid_environment() -> None:
    _, service_low, cost_low = run(None, level=20)
    _, service_high, cost_high = run(None, level=200)
    assert service_high > service_low  # more stock → better service …
    assert cost_high > cost_low  # … at a higher inventory cost


def test_supply_disruption_scenario_lowers_service() -> None:
    disruption = ScenarioSpec(
        scenario_id="supply_disruption",
        version="1.0.0",
        pack="warehouse",
        title="Supply disruption",
        parameters={
            "lead_time_delta": 7,
            "disruption_start_day": 7,
            "disruption_duration_days": 28,
            "supply_capacity_factor": 0.5,
        },
    )
    _, baseline, _ = run(None, level=60)
    _, disrupted, _ = run(disruption, level=60)
    assert disrupted < baseline
