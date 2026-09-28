"""Level-3 scenario checks (docs/validation.md §4) on the synthetic M5-shaped fixture.

Each registered warehouse scenario runs through the same pipeline (synthetic demand → forecast with
warm-up → inventory simulation × three strategies) with the same seed. The scenario layer supplies
configuration only; strategies are selected independently (Scenario ≠ Algorithm).
"""

from datetime import timedelta
from functools import cache

import pandas as pd
import pytest

from industrial_ai.foundation.datasets import Dataset
from industrial_ai.simulation import ComparisonResult
from industrial_ai_warehouse.scenarios import BUILTIN_SCENARIO_IDS, builtin_scenarios

from ..integration.strategy_support import STRATEGIES, demand, environment, run_strategies

pytestmark = pytest.mark.scenario_checks  # V3 in the validation report

SCENARIOS = builtin_scenarios()


@cache
def outcome(scenario_id: str) -> tuple[Dataset, ComparisonResult]:
    env = environment()
    scenario = SCENARIOS.get(scenario_id)
    horizon_demand = demand(env, scenario)
    return horizon_demand, run_strategies(env, horizon_demand, scenario)[1]


def daily_totals(scenario_id: str) -> pd.Series:
    frame = outcome(scenario_id)[0].data
    return frame.groupby("date")["quantity"].sum()


def metric(scenario_id: str, strategy: str, metric_id: str) -> float:
    value = outcome(scenario_id)[1].variants[strategy].metric(metric_id).value
    assert value is not None, (scenario_id, strategy, metric_id)
    return value


def orders(scenario_id: str, strategy: str = "reorder_point") -> pd.DataFrame:
    po = outcome(scenario_id)[1].variants[strategy].table("purchase_order").data
    start = pd.to_datetime(outcome("baseline")[0].data["date"]).min()
    return po.assign(day=(pd.to_datetime(po["order_date"]) - start).dt.days)


@pytest.mark.parametrize("scenario_id", BUILTIN_SCENARIO_IDS)
def test_every_scenario_runs_with_every_strategy(scenario_id: str) -> None:
    comparison = outcome(scenario_id)[1]
    assert list(comparison.variants) == list(STRATEGIES)
    for result in comparison.variants.values():
        assert result.scenario_result.scenario_id == scenario_id
        assert result.metric("fill_rate").value is not None


def expected_total(scenario_id: str) -> float:
    """Total expected demand: the scenario with sampling noise switched off (noise_scale = 0)."""
    env = environment()
    spec = SCENARIOS.get(scenario_id)
    noise_free = spec.model_copy(update={"parameters": {**spec.parameters, "noise_scale": 0.0}})
    return float(demand(env, noise_free).data["quantity"].sum())


def test_high_demand_raises_total_demand_by_about_30_percent() -> None:
    """validation.md §4: ratio ∈ [1.25, 1.35], measured on expected (noise-free) demand.

    Sampled totals on the small fixture carry Poisson noise of a few percent (sampled ratio ≈ 1.24),
    so the scenario effect is checked on expected demand; sampled demand must still rise clearly.
    """
    assert 1.25 <= expected_total("high_demand") / expected_total("baseline") <= 1.35
    assert daily_totals("high_demand").sum() / daily_totals("baseline").sum() > 1.15


def test_demand_shock_only_inside_its_window() -> None:
    shock, base = daily_totals("demand_shock"), daily_totals("baseline")
    day = pd.Series(range(len(base)), index=base.index)
    inside = (day >= 28) & (day < 42)
    assert shock[inside].mean() / base[inside].mean() == pytest.approx(2.5, rel=0.10)
    assert shock[~inside].mean() / base[~inside].mean() == pytest.approx(1.0, rel=0.05)


def test_supply_disruption_lengthens_lead_times_and_cuts_receipts_in_window() -> None:
    window = "28 <= day < 70"  # disruption_start_day 28, duration 42
    disrupted = orders("supply_disruption").query(window)
    baseline = orders("baseline").query(window)
    assert not disrupted.empty and not baseline.empty
    assert (
        disrupted["sampled_lead_time_days"].mean() >= baseline["sampled_lead_time_days"].mean() + 5
    )
    assert (disrupted["shipped_qty"] <= disrupted["quantity"]).all()
    assert disrupted["shipped_qty"].sum() < disrupted["quantity"].sum()
    outside = orders("supply_disruption").query("day < 28")
    assert (outside["shipped_qty"] == outside["quantity"]).all()


def test_static_strategy_responds_to_stress_scenarios() -> None:
    base = metric("baseline", "reorder_point", "stockout_day_rate")
    assert metric("high_demand", "reorder_point", "stockout_day_rate") >= base
    assert metric("supply_disruption", "reorder_point", "stockout_day_rate") >= base


def test_strategies_differ_under_baseline() -> None:
    fill = [metric("baseline", s, "fill_rate") for s in STRATEGIES]
    cost = [metric("baseline", s, "total_cost") for s in STRATEGIES]
    assert max(fill) - min(fill) >= 0.01 or max(cost) / min(cost) >= 1.05


def test_scenario_demand_uses_common_random_numbers() -> None:
    """Outside the shock window, demand_shock reproduces baseline demand exactly (same stream)."""
    shock, base = daily_totals("demand_shock"), daily_totals("baseline")
    first_window_day = shock.index[0] + timedelta(days=28)
    assert shock[shock.index < first_window_day].equals(base[base.index < first_window_day])
