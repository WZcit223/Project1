"""Direct no-look-ahead regression test (Gate 8 follow-up).

Change the synthetic demand strictly after a decision date D and rerun the whole pipeline.
Everything decided up to D (forecasts from origins ≤ D, ledger rows, orders placed, strategy
decisions) must be identical; later results must differ, proving the change is seen once it happens.
"""

from datetime import timedelta

import pandas as pd

from industrial_ai.foundation.datasets import Dataset, SourceInfo, SourceType, build_dataset
from industrial_ai.foundation.provenance import Lineage
from industrial_ai.simulation import SimulationResult

from .strategy_support import STRATEGIES, demand, environment, run_strategies

DECISION_DAY = 35


def tripled_after(original: Dataset, cutoff: pd.Timestamp) -> Dataset:
    data = original.data.copy()
    later = pd.to_datetime(data["date"]) > cutoff
    data.loc[later, "quantity"] = data.loc[later, "quantity"] * 3
    return build_dataset(
        dataset_id=f"{original.dataset_id}.tripled",
        version="1",
        schema=original.schema,
        data=data,
        source=SourceInfo(name="tripled demand (test)", source_type=SourceType.SYNTHETIC),
        lineage=Lineage(),
    )


def test_changing_future_demand_does_not_change_past_decisions() -> None:
    env = environment()
    cutoff = pd.Timestamp(env.start + timedelta(days=DECISION_DAY))
    base = demand(env, None)
    changed = tripled_after(base, cutoff)
    forecast_a, compare_a = run_strategies(env, base, None)
    forecast_b, compare_b = run_strategies(env, changed, None)

    # Forecasts made at origins ≤ D saw only data before their origin.
    def made_by(result: SimulationResult, before_or_on: bool) -> pd.DataFrame:
        assert result.prediction is not None
        frame = result.prediction.data
        origin = pd.to_datetime(frame["origin_date"])
        keep = origin <= cutoff if before_or_on else origin > cutoff
        return frame.loc[keep, ["origin_date", "date", "product_id", "store_id", "forecast"]]

    pd.testing.assert_frame_equal(made_by(forecast_a, True), made_by(forecast_b, True))
    assert not made_by(forecast_a, False).equals(made_by(forecast_b, False))

    for strategy in STRATEGIES:
        ledger_a = compare_a.variants[strategy].table("inventory_ledger").data
        ledger_b = compare_b.variants[strategy].table("inventory_ledger").data
        early = pd.to_datetime(ledger_a["date"]) <= cutoff
        # Ledger through day D, including the order decided on D (demand changes only after D).
        pd.testing.assert_frame_equal(ledger_a[early], ledger_b[early])
        assert not ledger_a[~early].equals(ledger_b[~early].set_axis(ledger_a[~early].index))

        orders_a = compare_a.variants[strategy].table("purchase_order").data
        orders_b = compare_b.variants[strategy].table("purchase_order").data
        placed = ["po_id", "order_date", "quantity", "shipped_qty", "sampled_lead_time_days"]
        early_a = orders_a[pd.to_datetime(orders_a["order_date"]) <= cutoff][placed]
        early_b = orders_b[pd.to_datetime(orders_b["order_date"]) <= cutoff][placed]
        pd.testing.assert_frame_equal(
            early_a.reset_index(drop=True), early_b.reset_index(drop=True)
        )
