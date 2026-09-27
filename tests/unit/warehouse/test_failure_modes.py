"""Failure modes of strategies and inventory simulation (Gate 8 follow-up, TASK-STR-004).

Sparse / zero demand, too few forecast errors, invalid forecast values, and supply disruptions that
start or end around review dates.
"""

import math
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest
from pydantic import JsonValue

from industrial_ai.core.errors import SimulationInputError
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.simulation import SimulationEngine, SimulationResult, new_simulation_registry
from industrial_ai_warehouse.simulation import InventorySimulationPlugin
from industrial_ai_warehouse.strategies import (
    DynamicParameters,
    DynamicStrategy,
    ForecastView,
    SafetyStockParameters,
    SafetyStockStrategy,
    builtin_strategies,
)

from .inventory_support import bundle, context, engine
from .test_strategies import START, item, observe


def reorder_point_run(demand: list[int], history_qty: int) -> tuple[pd.DataFrame, SimulationResult]:
    registry = new_simulation_registry()
    registry.register(InventorySimulationPlugin(builtin_strategies()))
    result = SimulationEngine(registry).run(
        "inventory_simulation",
        bundle(demand, history_qty=history_qty, on_hand=0),
        None,
        {"strategy_id": "reorder_point"},
        context(len(demand)),
    )
    return result.table("purchase_order").data, result


# --- sparse / zero demand ------------------------------------------------------------------


def test_no_history_means_no_orders_and_undefined_fill_rate() -> None:
    orders, result = reorder_point_run([0] * 14, history_qty=0)
    assert orders.empty
    assert result.metric("fill_rate").value is None  # no demand → undefined, not 1.0
    assert result.metric("purchase_orders").value == 0


def test_cold_start_item_with_demand_is_never_replenished() -> None:
    """v0.1 limitation: without history the reorder point is 0 and demand is lost."""
    orders, result = reorder_point_run([2] * 14, history_qty=0)
    assert orders.empty
    assert result.metric("fill_rate").value == 0.0
    assert result.metric("lost_sales_units").value == 28


def test_sparse_demand_keeps_accounting_identities() -> None:
    demand = [0, 0, 9, 0, 0, 0, 0, 14, 0, 0, 0, 1, 0, 0]
    ledger = (
        engine()
        .run(
            "inventory_simulation",
            bundle(demand, history_qty=0),
            None,
            {"strategy_id": "test_order_up_to", "strategy_parameters": {"level": 5}},
            context(len(demand)),
        )
        .table("inventory_ledger")
        .data
    )
    assert (ledger["fulfilled"] + ledger["lost_sales"] == ledger["demand"]).all()
    assert (ledger["closing_on_hand"] >= 0).all()


def test_zero_forecast_and_zero_errors_order_nothing() -> None:
    rows = [
        {"origin_date": START + timedelta(days=o), "date": START + timedelta(days=o + h),
         "forecast": 0.0, "actual": 0.0 if o + h < 0 else None}
        for o in (-56, -28, 0) for h in range(56)
    ]  # fmt: skip
    view = ForecastView(pd.DataFrame(rows))
    for strategy, params in (
        (SafetyStockStrategy(), SafetyStockParameters()),
        (DynamicStrategy(), DynamicParameters()),
    ):
        policy = strategy.create_policy(item(view), params)
        assert policy.order_quantity(observe(0, 0)) == 0.0


def test_sparse_forecast_errors_give_finite_positive_buffer() -> None:
    rows = []
    for o in (-56, -28, 0):
        for h in range(56):
            day = START + timedelta(days=o + h)
            actual = (20.0 if day.toordinal() % 9 == 0 else 0.0) if day < START else None
            rows.append({"origin_date": day - timedelta(days=h), "date": day, "forecast": 2.0,
                         "actual": actual})  # fmt: skip
    policy = DynamicStrategy().create_policy(
        item(ForecastView(pd.DataFrame(rows))), DynamicParameters()
    )
    quantity = policy.order_quantity(observe(0, 0))
    assert math.isfinite(quantity) and quantity > 2.0 * 16  # buffer above the mean cover


# --- too few forecast errors ----------------------------------------------------------------


def test_one_forecast_error_is_not_enough() -> None:
    origin = START - timedelta(days=1)
    rows = [
        {"origin_date": origin, "date": origin + timedelta(days=h),
         "forecast": 5.0, "actual": 4.0 if h == 0 else None}
        for h in range(56)
    ]  # fmt: skip
    policy = DynamicStrategy().create_policy(
        item(ForecastView(pd.DataFrame(rows))), DynamicParameters()
    )
    with pytest.raises(SimulationInputError, match="only 1 forecast errors"):
        policy.order_quantity(observe(0, 0))


# --- invalid forecast values ----------------------------------------------------------------


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0])
def test_invalid_forecast_values_are_rejected(bad: float) -> None:
    frame = pd.DataFrame(
        [
            {"origin_date": START, "date": START, "forecast": 3.0, "actual": None},
            {"origin_date": START, "date": START + timedelta(days=1), "forecast": bad,
             "actual": None},
        ]
    )  # fmt: skip
    with pytest.raises(SimulationInputError, match="invalid values"):
        ForecastView(frame)


# --- lead-time disruption around review dates ------------------------------------------------


def disrupted(start_day: int, duration: int) -> pd.DataFrame:
    parameters: dict[str, JsonValue] = {
        "lead_time_delta": 5,
        "disruption_start_day": start_day,
        "disruption_duration_days": duration,
    }
    scenario = ScenarioSpec(
        scenario_id="supply", version="1.0.0", pack="warehouse", title="s", parameters=parameters
    )
    result = engine().run(
        "inventory_simulation",
        bundle([3] * 21, review=7),
        scenario,
        {"strategy_id": "test_order_up_to", "strategy_parameters": {"level": 30}},
        context(21),
    )
    po = result.table("purchase_order").data
    return po.assign(day=(pd.to_datetime(po["order_date"]) - pd.Timestamp(START)).dt.days)


def lead_times(po: pd.DataFrame) -> dict[int, int]:
    return dict(zip(po["day"], po["sampled_lead_time_days"], strict=True))


def test_window_between_reviews_affects_no_order() -> None:
    # Reviews on days 0, 7, 14; the window days 1–6 contains no review day.
    assert lead_times(disrupted(1, 6)) == {0: 2, 7: 2, 14: 2}


def test_window_starting_on_a_review_day_affects_that_order() -> None:
    assert lead_times(disrupted(7, 1)) == {0: 2, 7: 7, 14: 2}


def test_window_ending_the_day_before_a_review_does_not_affect_it() -> None:
    assert lead_times(disrupted(8, 6)) == {0: 2, 7: 2, 14: 2}  # window days 8–13
    assert lead_times(disrupted(8, 7)) == {0: 2, 7: 2, 14: 7}  # window days 8–14


def test_orders_in_transit_when_the_window_starts_are_not_delayed() -> None:
    po = disrupted(1, 0)  # window from day 1 to the horizon end; day-0 order already placed
    assert lead_times(po)[0] == 2
    received = po.loc[po["day"] == 0, "received_date"].iloc[0]
    assert pd.Timestamp(received) == pd.Timestamp(START + timedelta(days=2))
    assert np.all(po.loc[po["day"] > 0, "sampled_lead_time_days"] == 7)
