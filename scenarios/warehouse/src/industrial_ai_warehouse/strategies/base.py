"""Replenishment strategy protocol (docs/plugin-spec.md §4).

A strategy is a pluggable ordering rule. For each item the inventory simulation asks the strategy
for an :class:`ItemPolicy` once (with everything known at the horizon start), then calls
``order_quantity`` on every review day. Strategies never change inventory: the simulation owns all
state transitions, rounding to case packs / minimum order quantities and purchase orders.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd
from pydantic import BaseModel

from industrial_ai.core.errors import SimulationInputError
from industrial_ai.core.registry import Registry


class ForecastView:
    """Read-only access to rolling forecasts as known on a given day (no look-ahead).

    On day ``t`` the view uses the latest forecast origin ≤ ``t``.
    """

    def __init__(self, forecasts: pd.DataFrame) -> None:
        """``forecasts``: rows (origin_date, date, forecast, actual) for one item."""
        frame = forecasts[["origin_date", "date", "forecast", "actual"]].copy()
        values = pd.to_numeric(frame["forecast"], errors="coerce").to_numpy(dtype="float64")
        invalid = ~np.isfinite(values) | (values < 0)
        if invalid.any():
            raise SimulationInputError(
                f"forecast has {int(invalid.sum())} invalid values (NaN, infinite or negative)"
            )
        frame["origin_date"] = pd.to_datetime(frame["origin_date"])
        frame["date"] = pd.to_datetime(frame["date"])
        self._frame = frame.sort_values(["origin_date", "date"]).reset_index(drop=True)
        self._origins = np.sort(self._frame["origin_date"].unique())

    def total(self, day: date, days: int) -> float:
        """Forecast demand summed over ``[day, day + days)`` from the latest origin ≤ ``day``."""
        origin = self._origin(day)
        start = pd.Timestamp(day)
        rows = self._frame[
            (self._frame["origin_date"] == origin)
            & (self._frame["date"] >= start)
            & (self._frame["date"] < start + pd.Timedelta(days=days))
        ]
        if len(rows) < days:
            raise ValueError(
                f"forecast from origin {origin.date()} covers only {len(rows)} of {days} days"
            )
        return float(rows["forecast"].sum())

    def recent_errors(self, day: date, days: int) -> np.ndarray:
        """Forecast errors (forecast − actual) for dates in ``[day − days, day)``.

        Each date's error comes from the latest origin ≤ that date, i.e. the forecast in use then.
        """
        start = pd.Timestamp(day) - pd.Timedelta(days=days)
        rows = self._frame[
            (self._frame["date"] >= start)
            & (self._frame["date"] < pd.Timestamp(day))
            & self._frame["actual"].notna()
        ]
        if rows.empty:
            return np.zeros(0)
        eligible = rows[rows["origin_date"] <= rows["date"]]
        latest = eligible.groupby("date")["origin_date"].transform("max")
        used = eligible[eligible["origin_date"] == latest]
        return (used["forecast"] - used["actual"]).to_numpy(dtype="float64")

    def _origin(self, day: date) -> pd.Timestamp:
        eligible = self._origins[self._origins <= np.datetime64(pd.Timestamp(day))]
        if len(eligible) == 0:
            raise ValueError(f"no forecast origin on or before {day}")
        return pd.Timestamp(eligible[-1])


@dataclass(frozen=True)
class ItemContext:
    """What a strategy knows about an item at the horizon start."""

    product_id: str
    warehouse_id: str
    history: np.ndarray
    """Daily demand history before the horizon (active period, leading zeros excluded)."""
    lead_time_mean_days: float
    """Mean lead time as known to the planner (includes the scenario delta if planner-aware)."""
    lead_time_std_days: float
    review_period_days: int
    order_cycle_days: int
    target_service_level: float
    forecast: ForecastView | None


@dataclass(frozen=True)
class DailyObservation:
    """State after demand on a review day (before ordering)."""

    day_index: int
    date: date
    on_hand: int
    on_order: int
    demand: int
    fulfilled: int

    @property
    def inventory_position(self) -> int:
        return self.on_hand + self.on_order


class ItemPolicy(Protocol):
    def order_quantity(self, observation: DailyObservation) -> float:
        """Units to order now (≥ 0, before rounding to case pack / minimum order quantity)."""
        ...


@runtime_checkable
class ReplenishmentStrategy(Protocol):
    strategy_id: str
    strategy_version: str
    description: str
    parameter_model: type[BaseModel]
    uses_forecast: bool
    """If true, the inventory simulation must receive an upstream forecast."""

    def create_policy(self, item: ItemContext, parameters: BaseModel) -> ItemPolicy:
        """Initialise the rule for one item from what is known at the horizon start."""
        ...


StrategyRegistry = Registry[ReplenishmentStrategy]


def new_strategy_registry() -> StrategyRegistry:
    return Registry("replenishment strategy", key=lambda s: (s.strategy_id, s.strategy_version))
