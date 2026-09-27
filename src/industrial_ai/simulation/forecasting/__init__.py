"""Forecast plugins (domain-neutral): seasonal naive, moving average and LightGBM."""

from industrial_ai.simulation.forecasting.baseline import (
    MovingAverageForecast,
    MovingAverageParameters,
    SeasonalNaiveForecast,
    SeasonalNaiveParameters,
)
from industrial_ai.simulation.forecasting.lightgbm_plugin import (
    LightGBMForecast,
    LightGBMParameters,
)
from industrial_ai.simulation.forecasting.rolling import ForecastParameters, forecast_schema

__all__ = [
    "ForecastParameters",
    "LightGBMForecast",
    "LightGBMParameters",
    "MovingAverageForecast",
    "MovingAverageParameters",
    "SeasonalNaiveForecast",
    "SeasonalNaiveParameters",
    "forecast_schema",
]
