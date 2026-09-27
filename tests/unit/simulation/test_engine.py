"""Tests for the simulation protocol, registry and engine (TASK-SIM-001, Gate 6)."""

from datetime import date

import pytest

from industrial_ai.core.errors import (
    DuplicatePluginError,
    PluginNotFoundError,
    SimulationError,
    SimulationInputError,
)
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.simulation import (
    PluginKind,
    RunContext,
    SimulationEngine,
    SimulationPlugin,
    SimulationResult,
    describe,
    new_simulation_registry,
    plugins_of_kind,
)

from .dummies import MeanForecast, StockSimulation, demand_dataset

CONTEXT = RunContext(run_id="run1", seed=7, start_date=date(2016, 1, 29), end_date=date(2016, 2, 4))
HIGH = ScenarioSpec(
    scenario_id="high_demand",
    version="1.0.0",
    pack="test",
    title="High",
    parameters={"demand_multiplier": 1.4, "lead_time_delta": 2},
)


def engine() -> SimulationEngine:
    registry = new_simulation_registry()
    registry.register(MeanForecast())
    registry.register(StockSimulation())
    return SimulationEngine(registry)


def forecast() -> SimulationResult:
    return engine().run("mean_forecast", demand_dataset(), None, {}, CONTEXT)


def test_plugins_satisfy_protocol_and_registry() -> None:
    assert isinstance(MeanForecast(), SimulationPlugin)
    registry = new_simulation_registry()
    registry.register(MeanForecast())
    registry.register(StockSimulation())
    with pytest.raises(DuplicatePluginError):
        registry.register(MeanForecast())
    assert [p.plugin_id for p in plugins_of_kind(registry, PluginKind.FORECAST)] == [
        "mean_forecast"
    ]
    info = describe(StockSimulation())
    assert info.kind is PluginKind.SIMULATION and "order_level" in str(info.parameter_schema)


def test_forecast_run_produces_traceable_prediction() -> None:
    result = forecast()
    assert result.prediction is not None
    assert result.prediction.metadata.row_count == 7 * 2
    assert result.prediction.dataset_id == "run1.mean_forecast.prediction"
    prov = result.prediction.provenance
    assert prov.component is not None and prov.component.id == "mean_forecast"
    assert prov.inputs[0].dataset_id == "demand" and prov.seed == 7
    assert result.metadata.status == "succeeded"
    assert result.metadata.input_hashes["demand"] == demand_dataset().metadata.content_hash
    assert result.metric("items").value == 2.0


def test_simulation_consumes_upstream_and_applies_scenario() -> None:
    upstream = forecast()
    result = engine().run(
        "stock_sim",
        demand_dataset(),
        HIGH,
        {"order_level": 6},
        CONTEXT.with_upstream("forecast", upstream),
    )
    ledger = result.table("ledger")
    assert ledger.metadata.row_count == 14
    assert result.scenario_result.applied_parameters == {"demand_multiplier": 1.4}
    assert any("lead_time_delta" in w for w in result.metadata.warnings)
    upstream_ids = {i.dataset_id for i in ledger.provenance.inputs}
    assert "run1.mean_forecast.prediction" in upstream_ids
    # demand A = 5 x 1.4 = 7 > 6 -> shortage 1/day for 7 days; B = 2.8 -> 3 <= 6
    assert result.metric("shortage_units").value == 7.0


def test_compare_runs_variants_on_identical_inputs() -> None:
    context = CONTEXT.with_upstream("forecast", forecast())
    comparison = engine().compare(
        "stock_sim",
        demand_dataset(),
        None,
        {"lean": {"order_level": 4}, "safe": {"order_level": 6}},
        context,
    )
    table = comparison.metrics_table()
    assert list(table.index) == ["lean", "safe"]
    assert table.loc["lean", "shortage_units"] == 7.0 and table.loc["safe", "shortage_units"] == 0.0
    assert comparison.variants["lean"].metadata.run_id == "run1.lean"


def test_runs_are_reproducible() -> None:
    first, second = forecast(), forecast()
    assert first.prediction is not None and second.prediction is not None
    assert first.prediction.metadata.content_hash == second.prediction.metadata.content_hash


def test_missing_inputs_upstream_and_bad_parameters_raise() -> None:
    with pytest.raises(PluginNotFoundError):
        engine().run("nope", demand_dataset(), None, {}, CONTEXT)
    with pytest.raises(SimulationInputError, match="upstream result 'forecast'"):
        engine().run("stock_sim", demand_dataset(), None, {"order_level": 1}, CONTEXT)
    with pytest.raises(SimulationInputError, match="invalid parameters"):
        engine().run("stock_sim", demand_dataset(), None, {"order_level": -1}, CONTEXT)
    with pytest.raises(SimulationInputError, match="compare"):
        engine().compare("stock_sim", demand_dataset(), None, {}, CONTEXT)


def test_missing_required_input_schema_raises() -> None:
    class NeedsSales(MeanForecast):
        plugin_id = "needs_sales"
        required_inputs: tuple[str, ...] = ("retail.sales",)

    registry = new_simulation_registry()
    registry.register(NeedsSales())
    with pytest.raises(SimulationInputError, match=r"retail\.sales"):
        SimulationEngine(registry).run("needs_sales", demand_dataset(), None, {}, CONTEXT)


def test_invalid_plugin_output_raises_instead_of_returning() -> None:
    with pytest.raises(SimulationError, match="failed validation"):
        engine().run("mean_forecast", demand_dataset(), None, {"negative": True}, CONTEXT)
