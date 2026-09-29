"""Strategy C ``dynamic``: periodic order-up-to, recomputed from the rolling forecast."""

import math

from pydantic import BaseModel

from industrial_ai_warehouse.strategies.base import DailyObservation, ItemContext, ItemPolicy
from industrial_ai_warehouse.strategies.common import (
    ForecastPolicyParameters,
    cycle_days,
    error_std,
    forecast_rate,
    forecast_view,
    z_value,
)


class DynamicParameters(ForecastPolicyParameters):
    pass


class _DynamicPolicy:
    def __init__(self, item: ItemContext, parameters: DynamicParameters) -> None:
        self.item = item
        self.view = forecast_view(item)
        self.z = z_value(item, parameters)
        self.cycle = cycle_days(item, parameters)
        self.error_window = parameters.error_window_days
        self.next_order_day = 0

    def order_quantity(self, observation: DailyObservation) -> float:
        if observation.day_index < self.next_order_day:
            return 0.0
        self.next_order_day = observation.day_index + self.cycle
        cover = self.item.lead_time_mean_days + self.cycle
        rate = forecast_rate(self.view, observation.date, cover)
        sigma = error_std(self.view, observation.date, self.error_window)
        order_up_to = rate * cover + self.z * sigma * math.sqrt(cover)
        return max(0.0, order_up_to - observation.inventory_position)


class DynamicStrategy:
    """Every R days: S_t = forecast over L̄ + R + z · σ_e,t · √(L̄ + R); order S_t − position."""

    strategy_id = "dynamic"
    strategy_version = "1.0.0"
    description = "Periodic order-up-to from the latest forecast and recent forecast errors."
    parameter_model: type[BaseModel] = DynamicParameters
    uses_forecast = True

    def create_policy(self, item: ItemContext, parameters: BaseModel) -> ItemPolicy:
        assert isinstance(parameters, DynamicParameters)
        return _DynamicPolicy(item, parameters)
