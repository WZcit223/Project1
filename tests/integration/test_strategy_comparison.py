"""Gate 8: the three replenishment strategies are compared on identical demand via engine.compare.

Fixture → M5 adapter → synthetic operations → scenario demand → demand timeline → rolling forecast
(from a warm-up period before the horizon) → inventory simulation × {reorder_point, safety_stock,
dynamic}.
"""

import pandas as pd

from industrial_ai.scenario import ScenarioSpec
from industrial_ai.simulation import ComparisonResult

from .strategy_support import STRATEGIES, demand, environment, run_strategies


def compare(scenario: ScenarioSpec | None) -> ComparisonResult:
    env = environment()
    return run_strategies(env, demand(env, scenario), scenario)[1]


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
