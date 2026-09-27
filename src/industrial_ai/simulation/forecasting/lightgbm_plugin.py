"""LightGBM forecast plugin ``lightgbm`` 1.0.0 (docs/simulation-api.md §4).

One global model over all series, **trained once on data before the horizon start** (Poisson
objective, deterministic single-threaded training seeded from the run). It predicts directly for
each horizon step ``h`` (no recursion). Features for target date ``d`` at origin ``o`` use only
observations before ``o``:

- ``h`` (days ahead), weekday and month of ``d``;
- last observed value; means of the last 7, 28 and 365 days;
- mean of the last 4 values on ``d``'s weekday.

Training samples come from synthetic origins every ``training_origin_step_days`` within the
``training_window_days`` before the horizon start, with targets strictly before the horizon start.
The goal is a working Data → Forecast → Simulation pipeline, not state-of-the-art accuracy.
"""

import lightgbm as lgb
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from industrial_ai.core.errors import SimulationInputError
from industrial_ai.foundation.datasets import Dataset, DatasetBundle
from industrial_ai.foundation.validation import ConstraintSet
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.simulation.base import PluginKind, PluginOutput, RunContext
from industrial_ai.simulation.forecasting.rolling import (
    ForecastParameters,
    horizon_index,
    observed_series,
    rolling_forecast,
)

FEATURES = (
    "horizon_day",
    "weekday",
    "month",
    "last_value",
    "mean_7",
    "mean_28",
    "mean_365",
    "mean_same_weekday_4",
)
_MIN_HISTORY_DAYS = 28


class LightGBMParameters(ForecastParameters):
    training_window_days: int = Field(default=730, ge=_MIN_HISTORY_DAYS * 2)
    training_origin_step_days: int = Field(default=7, ge=1)
    num_boost_round: int = Field(default=200, ge=1)
    learning_rate: float = Field(default=0.05, gt=0, le=1)
    num_leaves: int = Field(default=31, ge=2)
    min_data_in_leaf: int = Field(default=20, ge=1)


def features(
    history: np.ndarray, dates: pd.DatetimeIndex, origin: pd.Timestamp, horizon: int
) -> np.ndarray:
    """Feature matrix (horizon × entities rows, len(FEATURES) columns) from history before origin.

    ``history`` holds the observations (days × entities) ending the day before ``origin``;
    ``dates`` are their dates.
    """
    n_days, n_entities = history.shape

    def tail_mean(days: int) -> np.ndarray:
        result: np.ndarray = history[-days:].mean(axis=0)
        return result

    last, mean7, mean28, mean365 = history[-1], tail_mean(7), tail_mean(28), tail_mean(365)
    weekdays = dates.dayofweek.to_numpy()
    same_weekday = np.zeros((7, n_entities))
    for wd in range(7):
        rows = np.flatnonzero(weekdays == wd)[-4:]
        same_weekday[wd] = history[rows].mean(axis=0) if len(rows) else mean28
    blocks = []
    for h, target in enumerate(horizon_index(origin, horizon)):
        block = np.column_stack(
            [
                np.full(n_entities, h),
                np.full(n_entities, target.dayofweek),
                np.full(n_entities, target.month),
                last,
                mean7,
                mean28,
                mean365,
                same_weekday[target.dayofweek],
            ]
        )
        blocks.append(block)
    return np.vstack(blocks)


class LightGBMForecast:
    plugin_id = "lightgbm"
    plugin_version = "1.0.0"
    kind = PluginKind.FORECAST
    description = "Global LightGBM model (Poisson) with lag, rolling-mean and calendar features."
    parameter_model: type[BaseModel] = LightGBMParameters
    required_inputs: tuple[str, ...] = ()

    def run(
        self,
        dataset: Dataset | DatasetBundle,
        scenario: ScenarioSpec | None,
        parameters: BaseModel,
        constraints: ConstraintSet,
        context: RunContext,
    ) -> PluginOutput:
        assert isinstance(parameters, LightGBMParameters)
        p = parameters
        grid, _ = observed_series(dataset, p)
        start = pd.Timestamp(context.start_date)
        train_grid = grid[grid.index < start]
        x_train, y_train = _training_set(train_grid, p)
        booster = lgb.train(
            {
                "objective": "poisson",
                "learning_rate": p.learning_rate,
                "num_leaves": p.num_leaves,
                "min_data_in_leaf": p.min_data_in_leaf,
                "seed": context.seed,
                "deterministic": True,
                "force_row_wise": True,
                "num_threads": 1,
                "verbose": -1,
            },
            lgb.Dataset(x_train, y_train, feature_name=list(FEATURES), free_raw_data=True),
            num_boost_round=p.num_boost_round,
        )

        def predict(history: pd.DataFrame, origin: pd.Timestamp, horizon: int) -> pd.DataFrame:
            x = features(history.to_numpy(), pd.DatetimeIndex(history.index), origin, horizon)
            values = np.asarray(booster.predict(x), dtype="float64").reshape(
                horizon, history.shape[1]
            )
            return pd.DataFrame(
                values, index=horizon_index(origin, horizon), columns=history.columns
            )

        importance = booster.feature_importance(importance_type="gain")
        return rolling_forecast(
            dataset,
            p,
            context,
            predict,
            details={
                "training_rows": int(len(y_train)),
                "training_end": (start - pd.Timedelta(days=1)).date().isoformat(),
                "features": list(FEATURES),
                "feature_importance_gain": {
                    name: round(float(v), 3) for name, v in zip(FEATURES, importance, strict=True)
                },
            },
        )


def _training_set(grid: pd.DataFrame, p: LightGBMParameters) -> tuple[np.ndarray, np.ndarray]:
    horizon = p.forecast_horizon_days
    if len(grid) < _MIN_HISTORY_DAYS + horizon:
        raise SimulationInputError(
            f"lightgbm needs at least {_MIN_HISTORY_DAYS + horizon} days before the horizon start; "
            f"got {len(grid)}"
        )
    values = grid.to_numpy()
    dates = pd.DatetimeIndex(grid.index)
    last_origin = len(grid) - horizon  # targets of this origin end on the last training day
    first_origin = max(_MIN_HISTORY_DAYS, len(grid) - p.training_window_days)
    xs, ys = [], []
    for o in range(last_origin, first_origin - 1, -p.training_origin_step_days):
        xs.append(features(values[:o], dates[:o], dates[o], horizon))
        ys.append(values[o : o + horizon].reshape(-1))
    return np.vstack(xs), np.concatenate(ys)
