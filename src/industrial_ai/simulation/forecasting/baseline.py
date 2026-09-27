"""Baseline forecast plugins: ``seasonal_naive`` and ``moving_average`` (1.0.0)."""

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from industrial_ai.foundation.datasets import Dataset, DatasetBundle
from industrial_ai.foundation.validation import ConstraintSet
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.simulation.base import PluginKind, PluginOutput, RunContext
from industrial_ai.simulation.forecasting.rolling import (
    ForecastParameters,
    horizon_index,
    rolling_forecast,
)


class SeasonalNaiveParameters(ForecastParameters):
    season_length_days: int = Field(default=7, ge=1)
    seasons: int = Field(default=4, ge=1)
    """Average over the last N seasons (N = 1 is the classic seasonal naive)."""


class MovingAverageParameters(ForecastParameters):
    window_days: int = Field(default=28, ge=1)


class SeasonalNaiveForecast:
    plugin_id = "seasonal_naive"
    plugin_version = "1.0.0"
    kind = PluginKind.FORECAST
    description = "Same weekday in recent weeks: mean of the last N values one season apart."
    parameter_model: type[BaseModel] = SeasonalNaiveParameters
    required_inputs: tuple[str, ...] = ()

    def run(
        self,
        dataset: Dataset | DatasetBundle,
        scenario: ScenarioSpec | None,
        parameters: BaseModel,
        constraints: ConstraintSet,
        context: RunContext,
    ) -> PluginOutput:
        assert isinstance(parameters, SeasonalNaiveParameters)
        p = parameters

        def predict(history: pd.DataFrame, origin: pd.Timestamp, horizon: int) -> pd.DataFrame:
            index = horizon_index(origin, horizon)
            values = history.to_numpy()
            n = len(values)
            rows = []
            last = history.index[-1]
            for target in index:
                gap = (target - last).days  # days from the last observation to the target
                offset = (-gap) % p.season_length_days  # steps back to the same season position
                picks = [n - 1 - offset - k * p.season_length_days for k in range(p.seasons)]
                picks = [i for i in picks if i >= 0]
                rows.append(values[picks].mean(axis=0) if picks else np.zeros(values.shape[1]))
            return pd.DataFrame(rows, index=index, columns=history.columns)

        return rolling_forecast(dataset, p, context, predict)


class MovingAverageForecast:
    plugin_id = "moving_average"
    plugin_version = "1.0.0"
    kind = PluginKind.FORECAST
    description = "Flat forecast: mean of the last N days."
    parameter_model: type[BaseModel] = MovingAverageParameters
    required_inputs: tuple[str, ...] = ()

    def run(
        self,
        dataset: Dataset | DatasetBundle,
        scenario: ScenarioSpec | None,
        parameters: BaseModel,
        constraints: ConstraintSet,
        context: RunContext,
    ) -> PluginOutput:
        assert isinstance(parameters, MovingAverageParameters)
        window = parameters.window_days

        def predict(history: pd.DataFrame, origin: pd.Timestamp, horizon: int) -> pd.DataFrame:
            level = history.tail(window).mean(axis=0)
            index = horizon_index(origin, horizon)
            return pd.DataFrame([level.to_numpy()] * horizon, index=index, columns=history.columns)

        return rolling_forecast(dataset, parameters, context, predict)
