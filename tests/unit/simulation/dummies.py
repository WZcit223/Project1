"""Two minimal plugins that exercise the engine contract: a forecast and a stock simulation."""

from datetime import timedelta

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from industrial_ai.foundation.datasets import (
    Dataset,
    DatasetBundle,
    DatasetSchema,
    DType,
    FieldSpec,
    SourceInfo,
    SourceType,
    build_dataset,
)
from industrial_ai.foundation.provenance import Lineage
from industrial_ai.foundation.validation import ConstraintSet
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.simulation import Metric, OutputTable, PluginKind, PluginOutput, RunContext

DEMAND = DatasetSchema(
    schema_id="test.demand",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="date", dtype=DType.DATE),
        FieldSpec(name="item", dtype=DType.STR),
        FieldSpec(name="quantity", dtype=DType.INT, min=0),
    ),
    primary_key=("date", "item"),
    time_index="date",
)
FORECAST = DatasetSchema(
    schema_id="test.forecast",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="date", dtype=DType.DATE),
        FieldSpec(name="item", dtype=DType.STR),
        FieldSpec(name="forecast_qty", dtype=DType.FLOAT, min=0),
    ),
    primary_key=("date", "item"),
)
LEDGER = DatasetSchema(
    schema_id="test.ledger",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="date", dtype=DType.DATE),
        FieldSpec(name="item", dtype=DType.STR),
        FieldSpec(name="stock", dtype=DType.INT, min=0),
        FieldSpec(name="shortage", dtype=DType.INT, min=0),
    ),
    primary_key=("date", "item"),
)


def demand_dataset() -> Dataset:
    dates = pd.date_range("2016-01-01", periods=28, freq="D")
    frame = pd.concat(
        [
            pd.DataFrame({"date": dates, "item": item, "quantity": np.full(28, q)})
            for item, q in (("A", 5), ("B", 2))
        ],
        ignore_index=True,
    )
    return build_dataset(
        dataset_id="demand",
        version="1",
        schema=DEMAND,
        data=frame,
        source=SourceInfo(name="demand", source_type=SourceType.FIXTURE),
        lineage=Lineage(),
    )


class MeanForecastParams(BaseModel):
    window_days: int = Field(default=7, ge=1)
    negative: bool = False
    """Produce invalid (negative) forecasts — to test output validation."""


class MeanForecast:
    plugin_id = "mean_forecast"
    plugin_version = "1.0.0"
    kind = PluginKind.FORECAST
    description = "Mean of the last N days, repeated over the horizon (tests only)."
    parameter_model: type[BaseModel] = MeanForecastParams
    required_inputs: tuple[str, ...] = ("test.demand",)

    def run(
        self,
        dataset: Dataset | DatasetBundle,
        scenario: ScenarioSpec | None,
        parameters: BaseModel,
        constraints: ConstraintSet,
        context: RunContext,
    ) -> PluginOutput:
        assert isinstance(parameters, MeanForecastParams) and isinstance(dataset, Dataset)
        history = dataset.data
        recent = history[
            history["date"] > history["date"].max() - timedelta(days=parameters.window_days)
        ]
        means = recent.groupby("item")["quantity"].mean()
        dates = pd.date_range(context.start_date, context.end_date, freq="D")
        frame = pd.DataFrame(
            [
                {"date": d, "item": item, "forecast_qty": float(m)}
                for d in dates
                for item, m in means.items()
            ]
        )
        if parameters.negative:
            frame["forecast_qty"] = -frame["forecast_qty"]
        return PluginOutput(
            prediction=OutputTable(FORECAST, frame),
            metrics=(Metric(metric_id="items", value=float(len(means))),),
        )


class StockParams(BaseModel):
    order_level: int = Field(ge=0)


class StockSimulation:
    plugin_id = "stock_sim"
    plugin_version = "1.0.0"
    kind = PluginKind.SIMULATION
    description = (
        "Refill to order_level each day; demand = forecast x demand_multiplier (tests only)."
    )
    parameter_model: type[BaseModel] = StockParams
    required_inputs: tuple[str, ...] = ("test.demand",)

    def run(
        self,
        dataset: Dataset | DatasetBundle,
        scenario: ScenarioSpec | None,
        parameters: BaseModel,
        constraints: ConstraintSet,
        context: RunContext,
    ) -> PluginOutput:
        assert isinstance(parameters, StockParams)
        forecast = context.require_upstream("forecast").prediction
        assert forecast is not None
        multiplier, applied = 1.0, frozenset[str]()
        if scenario is not None and "demand_multiplier" in scenario.parameters:
            value = scenario.parameters["demand_multiplier"]
            assert isinstance(value, int | float)
            multiplier, applied = float(value), frozenset({"demand_multiplier"})
        frame = forecast.data.copy()
        demand = np.rint(frame["forecast_qty"] * multiplier).astype("int64")
        frame["stock"] = np.maximum(parameters.order_level - demand, 0)
        frame["shortage"] = np.maximum(demand - parameters.order_level, 0)
        total_demand = int(demand.sum())
        fill = None if total_demand == 0 else 1 - frame["shortage"].sum() / total_demand
        return PluginOutput(
            tables={"ledger": OutputTable(LEDGER, frame[["date", "item", "stock", "shortage"]])},
            metrics=(
                Metric(metric_id="service_level", value=fill, unit="ratio"),
                Metric(
                    metric_id="shortage_units", value=float(frame["shortage"].sum()), unit="units"
                ),
            ),
            applied_scenario_parameters=applied,
        )
