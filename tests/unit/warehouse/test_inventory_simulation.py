"""Tests for the inventory simulation plugin and KPIs (TASK-INV-001/002, Gate 7)."""

import numpy as np
import pandas as pd
import pytest
from pydantic import JsonValue

from industrial_ai.core.errors import PluginNotFoundError, SimulationInputError
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.simulation import SimulationResult

from .inventory_support import OrderUpToStrategy, bundle, context, engine


def simulate(
    demand: list[int],
    level: int,
    scenario: ScenarioSpec | None = None,
    seed: int = 1,
    **kwargs: object,
) -> SimulationResult:
    params: dict[str, JsonValue] = {
        "strategy_id": "test_order_up_to",
        "strategy_parameters": {"level": level},
    }
    return engine().run(
        "inventory_simulation",
        bundle(demand, **kwargs),  # type: ignore[arg-type]
        scenario,
        params,
        context(len(demand), seed),
    )


def ledger(result: SimulationResult) -> pd.DataFrame:
    return result.table("inventory_ledger").data


def orders(result: SimulationResult) -> pd.DataFrame:
    return result.table("purchase_order").data


def metric(result: SimulationResult, metric_id: str) -> float:
    value = result.metric(metric_id).value
    assert value is not None, metric_id
    return value


def supply(**parameters: JsonValue) -> ScenarioSpec:
    return ScenarioSpec(
        scenario_id="supply", version="1.0.0", pack="warehouse", title="s", parameters=parameters
    )


def test_hand_computed_ten_days() -> None:
    """on hand 10, demand 3/day, order up to 12 daily, lead time exactly 2 days."""
    result = simulate([3] * 10, level=12)
    frame = ledger(result)
    assert frame["closing_on_hand"].tolist() == [7, 4, 6, 6, 6, 6, 6, 6, 6, 6]
    assert frame["order_qty"].tolist() == [5] + [3] * 9
    assert frame["arrivals"].tolist() == [0, 0, 5] + [3] * 7
    assert frame["lost_sales"].sum() == 0
    po = orders(result)
    assert len(po) == 10
    assert (po["sampled_lead_time_days"] == 2).all()
    assert po["status"].tolist() == ["received"] * 8 + ["open"] * 2


def test_accounting_identities_hold() -> None:
    rng = np.random.default_rng(3)
    demand = rng.poisson(5, 90).tolist()
    frame = ledger(simulate(demand, level=20, lead_std=1.5, on_time=0.7))
    previous_close = frame["closing_on_hand"].shift(1, fill_value=10)
    assert (frame["opening_on_hand"] == previous_close + frame["arrivals"]).all()
    assert (frame["fulfilled"] + frame["lost_sales"] == frame["demand"]).all()
    assert (frame["closing_on_hand"] == frame["opening_on_hand"] - frame["fulfilled"]).all()
    assert (frame["inventory_position"] == frame["closing_on_hand"] + frame["on_order"]).all()
    assert (frame["closing_on_hand"] >= 0).all()


def test_metrics_match_their_definitions() -> None:
    demand = [3, 8, 0, 9, 4, 7, 2, 6, 5, 10, 1, 3, 7, 4]
    result = simulate(demand, level=9)
    frame, po = ledger(result), orders(result)
    t = len(demand)

    def value(metric_id: str) -> float:
        return metric(result, metric_id)

    assert value("demand_total") == sum(demand)
    assert value("service_level") == pytest.approx(frame["fulfilled"].sum() / sum(demand))
    assert value("stockout_rate") == pytest.approx((frame["lost_sales"] > 0).sum() / t)
    assert value("lost_sales_units") == frame["lost_sales"].sum()
    assert value("lost_sales_value") == pytest.approx(frame["lost_sales"].sum() * 2.0)
    assert value("avg_inventory_units") == pytest.approx(frame["closing_on_hand"].sum() / t)
    assert value("avg_inventory_value") == pytest.approx(frame["closing_on_hand"].sum() * 1.0 / t)
    assert value("holding_cost") == pytest.approx(
        frame["closing_on_hand"].sum() * 1.0 * 0.365 / 365
    )
    assert value("ordering_cost") == pytest.approx(len(po) * 10.0)
    assert value("inventory_cost") == pytest.approx(value("holding_cost") + value("ordering_cost"))
    assert value("order_frequency") == pytest.approx(len(po) / (t / 7))
    turnover = frame["fulfilled"].sum() / (frame["closing_on_hand"].sum() / t) * 365 / t
    assert value("inventory_turnover") == pytest.approx(turnover)
    assert result.metric("service_level", scope="product:P1").value == value("service_level")
    assert value("lost_sales_units") > 0  # this run has stockouts


def test_undefined_ratios_are_none() -> None:
    result = simulate([0] * 7, level=0, on_hand=0)
    assert result.metric("service_level").value is None
    assert result.metric("inventory_turnover").value is None


def test_rounding_to_case_pack_and_minimum_order_quantity() -> None:
    assert orders(simulate([3] * 5, level=12, case_pack=6))["quantity"].tolist()[0] == 6
    assert orders(simulate([3] * 5, level=12, case_pack=6, moq=13))["quantity"].tolist()[0] == 18


def test_supply_disruption_window_lead_time_and_capacity() -> None:
    scenario = supply(
        lead_time_delta=5,
        disruption_start_day=3,
        disruption_duration_days=4,
        supply_capacity_factor=0.5,
    )
    result = simulate([3] * 14, level=12, scenario=scenario)
    po = orders(result).set_index(result.table("purchase_order").data["order_date"].dt.day - 1)
    inside, outside = po.loc[3:6], po.drop(index=range(3, 7))
    assert (inside["sampled_lead_time_days"] == 7).all() and (
        outside["sampled_lead_time_days"] == 2
    ).all()
    assert (inside["shipped_qty"] == np.ceil(inside["quantity"] * 0.5)).all()
    assert (outside["shipped_qty"] == outside["quantity"]).all()
    assert set(result.scenario_result.applied_parameters) == {
        "lead_time_delta",
        "disruption_start_day",
        "disruption_duration_days",
        "supply_capacity_factor",
    }


def test_disruption_increases_stockouts() -> None:
    base = simulate([4] * 60, level=14)
    disrupted = simulate(
        [4] * 60, level=14, scenario=supply(lead_time_delta=7, supply_capacity_factor=0.5)
    )
    assert metric(disrupted, "lost_sales_units") > metric(base, "lost_sales_units")


def test_planner_awareness_changes_what_strategies_see() -> None:
    OrderUpToStrategy.seen.clear()
    simulate([3] * 5, level=12, scenario=supply(lead_time_delta=4))
    simulate([3] * 5, level=12, scenario=supply(lead_time_delta=4, planner_aware=True))
    assert [c.lead_time_mean_days for c in OrderUpToStrategy.seen] == [2.0, 6.0]


def test_late_deliveries_and_common_random_numbers() -> None:
    lean = orders(simulate([5] * 40, level=15, lead_std=1.0, on_time=0.0, seed=9))
    rich = orders(simulate([5] * 40, level=40, lead_std=1.0, on_time=0.0, seed=9))
    assert (lean["sampled_lead_time_days"] >= 2).all()  # every order late by 1-3 days
    common = lean.merge(rich, on="order_date", suffixes=("_lean", "_rich"))
    assert len(common) > 0
    assert (common["sampled_lead_time_days_lean"] == common["sampled_lead_time_days_rich"]).all()


def test_reproducible() -> None:
    first = simulate([5] * 30, level=15, lead_std=1.0, on_time=0.8, seed=4)
    second = simulate([5] * 30, level=15, lead_std=1.0, on_time=0.8, seed=4)
    assert (
        first.table("inventory_ledger").metadata.content_hash
        == second.table("inventory_ledger").metadata.content_hash
    )


def test_capacity_is_reported_not_enforced() -> None:
    result = simulate([1] * 5, level=50, capacity=20)
    assert any("capacity exceeded" in w for w in result.metadata.warnings)
    assert ledger(result)["closing_on_hand"].max() > 20


def test_input_errors() -> None:
    params: dict[str, JsonValue] = {
        "strategy_id": "test_needs_forecast",
        "strategy_parameters": {"level": 5},
    }
    with pytest.raises(SimulationInputError, match="needs the upstream forecast"):
        engine().run("inventory_simulation", bundle([3] * 5), None, params, context(5))
    with pytest.raises(SimulationInputError, match="does not cover the horizon"):
        engine().run(
            "inventory_simulation",
            bundle([3] * 5),
            None,
            {"strategy_id": "test_order_up_to", "strategy_parameters": {"level": 5}},
            context(8),
        )
    with pytest.raises(PluginNotFoundError):
        engine().run(
            "inventory_simulation", bundle([3] * 5), None, {"strategy_id": "nope"}, context(5)
        )
    with pytest.raises(SimulationInputError, match="invalid parameters for strategy"):
        engine().run(
            "inventory_simulation",
            bundle([3] * 5),
            None,
            {"strategy_id": "test_order_up_to"},
            context(5),
        )
    with pytest.raises(SimulationInputError, match="invalid supply"):
        simulate([3] * 5, level=5, scenario=supply(supply_capacity_factor=2.0))
