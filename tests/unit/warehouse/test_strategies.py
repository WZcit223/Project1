"""The three built-in replenishment strategies (docs/plugin-spec.md §4), checked by hand."""

import math
from datetime import date, timedelta
from statistics import NormalDist

import numpy as np
import pandas as pd
import pytest

from industrial_ai.core.errors import SimulationInputError
from industrial_ai_warehouse.strategies import (
    DailyObservation,
    DynamicParameters,
    DynamicStrategy,
    ForecastView,
    ItemContext,
    ReorderPointParameters,
    ReorderPointStrategy,
    SafetyStockParameters,
    SafetyStockStrategy,
    builtin_strategies,
)

START = date(2016, 1, 1)
Z95 = NormalDist().inv_cdf(0.95)


def forecasts(rates: dict[int, float], horizon: int = 56) -> ForecastView:
    """Origins at START + offset with a constant forecast; actuals alternate 4 / 6 before START."""
    rows = []
    for offset, rate in rates.items():
        origin = START + timedelta(days=offset)
        for h in range(horizon):
            day = origin + timedelta(days=h)
            actual = (4.0 if day.toordinal() % 2 else 6.0) if day < START else None
            rows.append({"origin_date": origin, "date": day, "forecast": rate, "actual": actual})
    return ForecastView(pd.DataFrame(rows))


def item(view: ForecastView | None = None, lead: float = 2.0) -> ItemContext:
    return ItemContext(
        product_id="P1",
        warehouse_id="WH01",
        history=np.array([2.0, 4.0, 3.0, 3.0]),
        lead_time_mean_days=lead,
        lead_time_std_days=0.5,
        review_period_days=1,
        order_cycle_days=14,
        target_service_level=0.95,
        forecast=view,
    )


def observe(day: int, position: int) -> DailyObservation:
    return DailyObservation(
        day_index=day,
        date=START + timedelta(days=day),
        on_hand=position,
        on_order=0,
        demand=0,
        fulfilled=0,
    )


def warm_errors_std() -> float:
    days = [START - timedelta(days=d) for d in range(56, 0, -1)]
    errors = [5.0 - (4.0 if d.toordinal() % 2 else 6.0) for d in days]
    return float(np.std(errors, ddof=1))


def test_builtin_registry_has_three_strategies() -> None:
    registry = builtin_strategies()
    uses = {s.strategy_id: s.uses_forecast for s in registry.list()}
    assert uses == {"reorder_point": False, "safety_stock": True, "dynamic": True}


def test_reorder_point_orders_q_at_or_below_s() -> None:
    # μ_hist = 3, L̄ = 2, R = 14 → s = 6, Q = 42
    policy = ReorderPointStrategy().create_policy(item(), ReorderPointParameters())
    assert policy.order_quantity(observe(0, 7)) == 0.0
    assert policy.order_quantity(observe(1, 6)) == pytest.approx(42.0)
    custom = ReorderPointStrategy().create_policy(item(), ReorderPointParameters(cycle_days=7))
    assert custom.order_quantity(observe(0, 0)) == pytest.approx(21.0)


def test_reorder_point_without_history_never_orders() -> None:
    context = item()
    empty = ItemContext(**{**context.__dict__, "history": np.zeros(0)})
    policy = ReorderPointStrategy().create_policy(empty, ReorderPointParameters())
    assert policy.order_quantity(observe(0, 0)) == 0.0


def test_safety_stock_levels_by_hand_and_fixed_after_start() -> None:
    view = forecasts({-56: 5.0, -49: 5.0, -42: 5.0, -35: 5.0, -28: 5.0, -21: 5.0, -14: 5.0,
                      -7: 5.0, 0: 5.0, 7: 10.0})  # fmt: skip
    policy = SafetyStockStrategy().create_policy(item(view), SafetyStockParameters())
    sigma = warm_errors_std()
    reorder_point = 5.0 * 2 + Z95 * sigma * math.sqrt(2)
    order_up_to = reorder_point + 5.0 * 14
    assert policy.order_quantity(observe(0, 20)) == 0.0  # position 20 > s ≈ 13.3
    assert policy.order_quantity(observe(1, 10)) == pytest.approx(order_up_to - 10)
    # The forecast doubles from day 7, but (s, S) stay fixed.
    assert policy.order_quantity(observe(8, 10)) == pytest.approx(order_up_to - 10)


def test_dynamic_orders_every_cycle_and_follows_the_forecast() -> None:
    view = forecasts({-56: 5.0, -49: 5.0, -42: 5.0, -35: 5.0, -28: 5.0, -21: 5.0, -14: 5.0,
                      -7: 5.0, 0: 5.0, 7: 5.0, 14: 10.0})  # fmt: skip
    policy = DynamicStrategy().create_policy(item(view), DynamicParameters())
    sigma = warm_errors_std()
    cover = 2 + 14
    assert policy.order_quantity(observe(0, 0)) == pytest.approx(
        5.0 * cover + Z95 * sigma * math.sqrt(cover)
    )
    assert policy.order_quantity(observe(1, 0)) == 0.0  # not an order day
    assert policy.order_quantity(observe(13, 0)) == 0.0
    # Day 14: the latest origin (14) forecasts 10/day; σ_e now also includes horizon errors.
    errors = view.recent_errors(START + timedelta(days=14), 56)
    expected = 10.0 * cover + Z95 * float(np.std(errors, ddof=1)) * math.sqrt(cover)
    assert policy.order_quantity(observe(14, 30)) == pytest.approx(expected - 30)


def test_dynamic_never_orders_negative() -> None:
    view = forecasts({-56: 5.0, -28: 5.0, 0: 5.0})
    policy = DynamicStrategy().create_policy(item(view), DynamicParameters())
    assert policy.order_quantity(observe(0, 10_000)) == 0.0


def test_service_level_parameter_overrides_item_target() -> None:
    view = forecasts({-56: 5.0, -28: 5.0, 0: 5.0})
    high = DynamicStrategy().create_policy(item(view), DynamicParameters(service_level=0.99))
    base = DynamicStrategy().create_policy(item(view), DynamicParameters())
    assert high.order_quantity(observe(0, 0)) > base.order_quantity(observe(0, 0))


def test_forecast_strategies_need_warm_up_errors() -> None:
    view = forecasts({0: 5.0})  # no forecast before the horizon → no errors to estimate σ_e
    for strategy, params in (
        (SafetyStockStrategy(), SafetyStockParameters()),
        (DynamicStrategy(), DynamicParameters()),
    ):
        policy = strategy.create_policy(item(view), params)
        with pytest.raises(SimulationInputError, match="warm-up"):
            policy.order_quantity(observe(0, 0))


def test_forecast_strategies_need_enough_forecast_horizon() -> None:
    view = forecasts({-56: 5.0, -28: 5.0, 0: 5.0}, horizon=10)
    policy = DynamicStrategy().create_policy(item(view), DynamicParameters())
    with pytest.raises(SimulationInputError, match="forecast_horizon_days"):
        policy.order_quantity(observe(0, 0))


def test_forecast_strategies_need_a_forecast() -> None:
    with pytest.raises(SimulationInputError, match="no forecast"):
        DynamicStrategy().create_policy(item(None), DynamicParameters())
