"""Rolling-origin forecasting shared by all forecast plugins (docs/simulation-api.md §4).

At each forecast origin ``o`` (horizon start, then every ``reforecast_interval_days``) a predictor
sees **only observations dated before ``o``** and predicts ``o … o + forecast_horizon_days − 1``.
Actual values (where the input contains them) are attached afterwards for accuracy metrics only.
"""

from collections.abc import Callable
from datetime import date, timedelta

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from industrial_ai.core.errors import SimulationInputError
from industrial_ai.foundation.datasets import (
    Dataset,
    DatasetBundle,
    DatasetSchema,
    DType,
    FieldSpec,
)
from industrial_ai.simulation.base import Metric, OutputTable, PluginOutput, RunContext

ENTITY_SEPARATOR = "\x1f"

Predictor = Callable[[pd.DataFrame, pd.Timestamp, int], pd.DataFrame]
"""(history before the origin as dates × entities, origin, horizon days) → forecasts."""


class ForecastParameters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_columns: tuple[str, ...] = Field(min_length=1)
    time_column: str = "date"
    value_column: str = "quantity"
    input_table: str | None = None
    """Table name when the input is a bundle."""
    reforecast_interval_days: int = Field(default=7, ge=1)
    forecast_horizon_days: int = Field(default=28, ge=1)


def forecast_schema(entity_columns: tuple[str, ...]) -> DatasetSchema:
    return DatasetSchema(
        schema_id="sim.forecast",
        schema_version="1.0.0",
        fields=(
            FieldSpec(name="origin_date", dtype=DType.DATE),
            FieldSpec(name="date", dtype=DType.DATE),
            *(FieldSpec(name=c, dtype=DType.STR) for c in entity_columns),
            FieldSpec(name="forecast", dtype=DType.FLOAT, min=0),
            FieldSpec(name="actual", dtype=DType.FLOAT, nullable=True),
        ),
        primary_key=("origin_date", "date", *entity_columns),
        entity_keys=entity_columns,
        description="Rolling-origin forecasts with actuals attached where observed.",
    )


def observed_series(
    dataset: Dataset | DatasetBundle, p: ForecastParameters
) -> tuple[pd.DataFrame, int]:
    """Daily grid (dates × entity keys) of observed values; returns (grid, filled cell count).

    Missing (date, entity) cells inside the observed date range are filled with 0 and counted.
    """
    table = _input_table(dataset, p)
    needed = [p.time_column, *p.entity_columns, p.value_column]
    missing = sorted(set(needed) - set(table.data.columns))
    if missing:
        raise SimulationInputError(f"forecast input {table.ref} lacks columns {missing}")
    frame = table.data[needed].copy()
    frame[p.time_column] = pd.to_datetime(frame[p.time_column])
    key = frame[p.entity_columns[0]].astype(str)
    for column in p.entity_columns[1:]:
        key = key + ENTITY_SEPARATOR + frame[column].astype(str)
    frame["_key"] = key
    grid = frame.pivot_table(
        index=p.time_column, columns="_key", values=p.value_column, aggfunc="sum"
    ).sort_index()
    full_index = pd.date_range(grid.index.min(), grid.index.max(), freq="D")
    grid = grid.reindex(full_index)
    filled = int(grid.isna().sum().sum())
    return grid.fillna(0.0).astype("float64"), filled


def rolling_forecast(
    dataset: Dataset | DatasetBundle,
    p: ForecastParameters,
    context: RunContext,
    predictor: Predictor,
    details: dict[str, JsonValue] | None = None,
) -> PluginOutput:
    grid, filled = observed_series(dataset, p)
    origins = _origins(context.start_date, context.end_date, p.reforecast_interval_days)
    parts = []
    for origin in origins:
        history = grid[grid.index < origin]
        if history.empty:
            raise SimulationInputError(f"no observations before forecast origin {origin.date()}")
        predicted = predictor(history, origin, p.forecast_horizon_days)
        expected_index = pd.date_range(origin, periods=p.forecast_horizon_days, freq="D")
        if not predicted.index.equals(expected_index) or list(predicted.columns) != list(
            grid.columns
        ):
            raise SimulationInputError("predictor returned forecasts with an unexpected shape")
        long = _long(predicted, "forecast")
        long.insert(0, "origin_date", origin)
        parts.append(long)
    result = pd.concat(parts, ignore_index=True)
    result = result.merge(_long(grid, "actual"), on=["date", "_key"], how="left")
    keys = result["_key"].str.split(ENTITY_SEPARATOR, expand=True)
    for i, column in enumerate(p.entity_columns):
        result[column] = keys[i]
    result["forecast"] = result["forecast"].clip(lower=0.0).astype("float64")
    columns = ["origin_date", "date", *p.entity_columns, "forecast", "actual"]
    result = (
        result[columns]
        .sort_values(["origin_date", "date", *p.entity_columns])
        .reset_index(drop=True)
    )
    warnings = (f"{filled} missing (date, entity) observations filled with 0",) if filled else ()
    return PluginOutput(
        prediction=OutputTable(forecast_schema(p.entity_columns), result),
        metrics=accuracy_metrics(result),
        warnings=warnings,
        details={
            "origins": [o.date().isoformat() for o in origins],
            "series": int(grid.shape[1]),
            **(details or {}),
        },
    )


def accuracy_metrics(forecasts: pd.DataFrame) -> tuple[Metric, ...]:
    """MAE, RMSE, WAPE and bias over all forecast rows that have an observed actual."""
    rows = forecasts.dropna(subset=["actual"])
    n = len(rows)
    error = rows["forecast"] - rows["actual"]
    total_actual = float(rows["actual"].sum())
    return (
        Metric(metric_id="forecast_rows_evaluated", value=float(n), unit="rows"),
        Metric(metric_id="mae", value=float(error.abs().mean()) if n else None, unit="units"),
        Metric(
            metric_id="rmse", value=float(np.sqrt((error**2).mean())) if n else None, unit="units"
        ),
        Metric(
            metric_id="wape",
            value=float(error.abs().sum() / total_actual) if total_actual > 0 else None,
            unit="ratio",
        ),
        Metric(
            metric_id="bias",
            value=float(error.sum() / total_actual) if total_actual > 0 else None,
            unit="ratio",
        ),
    )


def _long(frame: pd.DataFrame, value_name: str) -> pd.DataFrame:
    """dates × entity keys → rows (date, _key, value)."""
    return (
        frame.rename_axis(index="date", columns="_key")
        .reset_index()
        .melt(id_vars="date", var_name="_key", value_name=value_name)
    )


def horizon_index(origin: pd.Timestamp, horizon: int) -> pd.DatetimeIndex:
    return pd.date_range(origin, periods=horizon, freq="D")


def _origins(start: date, end: date, interval: int) -> list[pd.Timestamp]:
    if end < start:
        raise SimulationInputError(f"horizon end {end} is before start {start}")
    days = (end - start).days
    return [pd.Timestamp(start + timedelta(days=d)) for d in range(0, days + 1, interval)]


def _input_table(dataset: Dataset | DatasetBundle, p: ForecastParameters) -> Dataset:
    if isinstance(dataset, Dataset):
        return dataset
    if p.input_table is None:
        raise SimulationInputError(
            f"input is bundle {dataset.ref}; set input_table (one of {sorted(dataset.tables)})"
        )
    if p.input_table not in dataset.tables:
        raise SimulationInputError(f"bundle {dataset.ref} has no table {p.input_table!r}")
    return dataset.tables[p.input_table]
