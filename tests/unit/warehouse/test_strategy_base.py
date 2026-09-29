"""Tests for the strategy protocol helpers: ForecastView (no look-ahead) and the registry."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from industrial_ai.core.errors import DuplicatePluginError
from industrial_ai_warehouse.strategies import (
    DailyObservation,
    ForecastView,
    ReplenishmentStrategy,
    new_strategy_registry,
)

from .inventory_support import OrderUpToStrategy


def forecasts() -> pd.DataFrame:
    """Origins Jan 1 (5/day) and Jan 8 (7/day), 14 days each; actuals 6/day until Jan 11."""
    rows = []
    for origin, level in ((pd.Timestamp("2016-01-01"), 5.0), (pd.Timestamp("2016-01-08"), 7.0)):
        for d in pd.date_range(origin, periods=14, freq="D"):
            actual = 6.0 if d < pd.Timestamp("2016-01-12") else np.nan
            rows.append({"origin_date": origin, "date": d, "forecast": level, "actual": actual})
    return pd.DataFrame(rows)


def test_total_uses_latest_origin_on_or_before_the_day() -> None:
    view = ForecastView(forecasts())
    assert view.total(date(2016, 1, 3), 5) == 25.0  # origin Jan 1
    assert view.total(date(2016, 1, 8), 5) == 35.0  # origin Jan 8
    assert view.total(date(2016, 1, 10), 3) == 21.0
    with pytest.raises(ValueError, match="no forecast origin"):
        view.total(date(2015, 12, 31), 3)
    with pytest.raises(ValueError, match="covers only"):
        view.total(date(2016, 1, 20), 5)


def test_recent_errors_use_the_forecast_in_use_on_each_date() -> None:
    view = ForecastView(forecasts())
    errors = view.recent_errors(date(2016, 1, 12), 6)  # dates Jan 6 .. Jan 11
    # Jan 6-7 from origin Jan 1 (5 - 6 = -1), Jan 8-11 from origin Jan 8 (7 - 6 = +1)
    assert sorted(errors.tolist()) == [-1.0, -1.0, 1.0, 1.0, 1.0, 1.0]
    assert view.recent_errors(date(2016, 1, 1), 5).size == 0


def test_observation_position_and_registry() -> None:
    observation = DailyObservation(
        day_index=0, date=date(2016, 1, 1), on_hand=4, on_order=6, demand=3, fulfilled=3
    )
    assert observation.inventory_position == 10
    assert isinstance(OrderUpToStrategy(), ReplenishmentStrategy)
    registry = new_strategy_registry()
    registry.register(OrderUpToStrategy())
    with pytest.raises(DuplicatePluginError):
        registry.register(OrderUpToStrategy())
