"""Strategy A ``reorder_point`` (s, Q): static, history-based, no safety stock."""

from pydantic import BaseModel

from industrial_ai_warehouse.strategies.base import DailyObservation, ItemContext, ItemPolicy
from industrial_ai_warehouse.strategies.common import CycleParameters, cycle_days


class ReorderPointParameters(CycleParameters):
    pass


class _ReorderPointPolicy:
    def __init__(self, reorder_point: float, quantity: float) -> None:
        self.reorder_point = reorder_point
        self.quantity = quantity

    def order_quantity(self, observation: DailyObservation) -> float:
        if observation.inventory_position <= self.reorder_point:
            return self.quantity
        return 0.0


class ReorderPointStrategy:
    """s = μ_hist · L̄; order Q = μ_hist · R when the inventory position ≤ s."""

    strategy_id = "reorder_point"
    strategy_version = "1.0.0"
    description = "Reorder point (s, Q) from mean historical demand; no safety stock."
    parameter_model: type[BaseModel] = ReorderPointParameters
    uses_forecast = False

    def create_policy(self, item: ItemContext, parameters: BaseModel) -> ItemPolicy:
        assert isinstance(parameters, ReorderPointParameters)
        mean = float(item.history.mean()) if len(item.history) else 0.0
        return _ReorderPointPolicy(
            reorder_point=mean * item.lead_time_mean_days,
            quantity=mean * cycle_days(item, parameters),
        )
