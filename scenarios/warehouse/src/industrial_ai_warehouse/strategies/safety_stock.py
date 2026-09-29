"""Strategy B ``safety_stock`` (s, S): forecast-based, parameters fixed at the horizon start."""

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


class SafetyStockParameters(ForecastPolicyParameters):
    pass


class _SafetyStockPolicy:
    def __init__(self, item: ItemContext, parameters: SafetyStockParameters) -> None:
        self.item = item
        self.view = forecast_view(item)
        self.z = z_value(item, parameters)
        self.cycle = cycle_days(item, parameters)
        self.error_window = parameters.error_window_days
        self.levels: tuple[float, float] | None = None
        """(s, S), set at the first review (the horizon start) and then kept fixed."""

    def order_quantity(self, observation: DailyObservation) -> float:
        if self.levels is None:
            self.levels = self._levels(observation)
        reorder_point, order_up_to = self.levels
        position = observation.inventory_position
        return order_up_to - position if position <= reorder_point else 0.0

    def _levels(self, observation: DailyObservation) -> tuple[float, float]:
        lead = self.item.lead_time_mean_days
        rate = forecast_rate(self.view, observation.date, lead + self.cycle)
        sigma = error_std(self.view, observation.date, self.error_window)
        safety_stock = self.z * sigma * math.sqrt(lead)
        reorder_point = rate * lead + safety_stock
        return reorder_point, reorder_point + rate * self.cycle


class SafetyStockStrategy:
    """SS = z · σ_e · √L̄; s = μ_f · L̄ + SS; S = s + μ_f · R; order S − position when ≤ s."""

    strategy_id = "safety_stock"
    strategy_version = "1.0.0"
    description = "Safety stock (s, S) from the forecast at the horizon start; fixed thereafter."
    parameter_model: type[BaseModel] = SafetyStockParameters
    uses_forecast = True

    def create_policy(self, item: ItemContext, parameters: BaseModel) -> ItemPolicy:
        assert isinstance(parameters, SafetyStockParameters)
        return _SafetyStockPolicy(item, parameters)
