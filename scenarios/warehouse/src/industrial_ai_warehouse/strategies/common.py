"""Shared helpers for the built-in replenishment strategies (docs/plugin-spec.md §4)."""

import math
from datetime import date, timedelta
from statistics import NormalDist

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from industrial_ai.core.errors import SimulationInputError
from industrial_ai_warehouse.strategies.base import ForecastView, ItemContext


class CycleParameters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cycle_days: int | None = Field(default=None, ge=1)
    """Order cycle R in days; ``None`` uses the item's ``order_cycle_days``."""


class ForecastPolicyParameters(CycleParameters):
    service_level: float | None = Field(default=None, gt=0.5, lt=1.0)
    """Target service level for z; ``None`` uses the item's ``target_service_level``."""
    error_window_days: int = Field(default=56, ge=14)
    """Past days whose forecast errors estimate σ_e."""


def cycle_days(item: ItemContext, parameters: CycleParameters) -> int:
    return parameters.cycle_days if parameters.cycle_days is not None else item.order_cycle_days


def z_value(item: ItemContext, parameters: ForecastPolicyParameters) -> float:
    level = parameters.service_level or item.target_service_level
    return NormalDist().inv_cdf(level)


def forecast_view(item: ItemContext) -> ForecastView:
    if item.forecast is None:
        raise SimulationInputError(f"no forecast for {item.product_id}/{item.warehouse_id}")
    return item.forecast


def forecast_rate(view: ForecastView, today: date, days: float) -> float:
    """Mean forecast daily demand over the ``days`` after ``today`` (no look-ahead)."""
    n = max(1, math.ceil(days))
    try:
        return view.total(today + timedelta(days=1), n) / n
    except ValueError as exc:
        raise SimulationInputError(
            f"forecast does not cover the next {n} days after {today}: {exc}; "
            "increase forecast_horizon_days"
        ) from exc


def error_std(view: ForecastView, today: date, window_days: int) -> float:
    """Standard deviation of daily forecast errors in the ``window_days`` up to ``today``.

    Needs forecasts from before the horizon start (run the forecast with a warm-up period).
    """
    errors = view.recent_errors(today, window_days)
    if len(errors) < 2:
        raise SimulationInputError(
            f"only {len(errors)} forecast errors in the {window_days} days before {today}; "
            "start the forecast run earlier than the simulation horizon (warm-up)"
        )
    return float(np.std(errors, ddof=1))
