"""Replenishment strategies (pluggable ordering rules used by the inventory simulation)."""

from industrial_ai_warehouse.strategies.base import (
    DailyObservation,
    ForecastView,
    ItemContext,
    ItemPolicy,
    ReplenishmentStrategy,
    StrategyRegistry,
    new_strategy_registry,
)
from industrial_ai_warehouse.strategies.dynamic import DynamicParameters, DynamicStrategy
from industrial_ai_warehouse.strategies.reorder_point import (
    ReorderPointParameters,
    ReorderPointStrategy,
)
from industrial_ai_warehouse.strategies.safety_stock import (
    SafetyStockParameters,
    SafetyStockStrategy,
)


def builtin_strategies() -> StrategyRegistry:
    """Registry with the three v0.1 strategies: reorder_point, safety_stock, dynamic."""
    registry = new_strategy_registry()
    registry.register(ReorderPointStrategy())
    registry.register(SafetyStockStrategy())
    registry.register(DynamicStrategy())
    return registry


__all__ = [
    "DailyObservation",
    "DynamicParameters",
    "DynamicStrategy",
    "ForecastView",
    "ItemContext",
    "ItemPolicy",
    "ReorderPointParameters",
    "ReorderPointStrategy",
    "ReplenishmentStrategy",
    "SafetyStockParameters",
    "SafetyStockStrategy",
    "StrategyRegistry",
    "builtin_strategies",
    "new_strategy_registry",
]
