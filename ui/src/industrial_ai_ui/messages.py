"""UI labels in one place (English v0.1; a Chinese catalog can be added alongside)."""

METRIC_LABELS: dict[str, str] = {
    "fill_rate": "Fill rate",
    "stockout_day_rate": "Stockout-day rate",
    "stockout_days": "Stockout days",
    "lost_sales_units": "Unfulfilled demand (units)",
    "demand_total": "Demand (units)",
    "avg_on_hand_units": "Avg on-hand (units)",
    "avg_on_hand_value": "Avg on-hand value",
    "inventory_turnover": "Inventory turnover (/yr)",
    "purchase_orders": "Purchase orders",
    "units_ordered": "Units ordered",
    "order_frequency": "Orders / item / week",
    "ordering_cost": "Ordering cost",
    "holding_cost": "Holding cost",
    "inventory_cost": "Inventory cost (ordering + holding)",
    "lost_sales_cost": "Lost-sales cost",
    "total_cost": "Total cost",
}
"""Management KPIs in display order."""

RATIO_METRICS = frozenset({"fill_rate", "stockout_day_rate"})
MONEY_METRICS = frozenset(
    {
        "avg_on_hand_value",
        "ordering_cost",
        "holding_cost",
        "inventory_cost",
        "lost_sales_cost",
        "total_cost",
    }
)

STRATEGY_LABELS: dict[str, str] = {
    "reorder_point": "Reorder point",
    "safety_stock": "Safety stock",
    "dynamic": "Dynamic",
}

DEFAULT_SCENARIO = "baseline"
"""Preselected on the Simulation page; scenarios are listed by id, so user ones may sort first."""

DEFAULT_FORECAST_MODEL = "seasonal_naive"
"""Preselected on the Simulation page: the model the demo guide, scripts/demo.py and the validation
report use, so a first run with the default form reproduces the documented numbers."""

HONESTY_BADGE = "Prototype · Synthetic data"
HONESTY_NOTE = (
    "Results come from simulated operations on synthetic demand calibrated to reference data. "
    "They show how the framework compares strategies under controlled conditions; they are not "
    "evidence of real-world performance."
)
