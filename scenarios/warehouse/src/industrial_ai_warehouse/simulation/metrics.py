"""Inventory KPIs exactly as defined in docs/data-model.md §6.

Notation per item i and day t: demand D, fulfilled F, lost L = D − F, closing on-hand I, unit
cost c, unit price p, annual holding rate h, order cost k, horizon T days, N items. Undefined
ratios are ``None``, never a substitute number.

Cost components are reported separately and never mixed silently:
``inventory_cost = ordering_cost + holding_cost`` and
``total_cost = inventory_cost + lost_sales_cost``.
"""

import pandas as pd

from industrial_ai.simulation import Metric


def inventory_metrics(
    ledger: pd.DataFrame,
    purchase_orders: pd.DataFrame,
    items: pd.DataFrame,
    order_cost_by_supplier: dict[str, float],
    horizon_days: int,
) -> tuple[Metric, ...]:
    """KPIs over the horizon.

    ``items``: one row per (product_id, warehouse_id) with ``unit_cost``, ``unit_price`` and
    ``holding_cost_rate_annual``.
    """
    frame = ledger.merge(
        items, on=["product_id", "warehouse_id"], how="left", validate="many_to_one"
    )
    if frame[["unit_cost", "unit_price", "holding_cost_rate_annual"]].isna().any().any():
        raise ValueError("cost data missing for some ledger items")
    n_items = len(items)
    t = horizon_days
    demand = float(frame["demand"].sum())
    fulfilled = float(frame["fulfilled"].sum())
    lost = float(frame["lost_sales"].sum())
    value = frame["closing_on_hand"] * frame["unit_cost"]
    avg_on_hand_value = float(value.sum()) / t
    holding = float((value * frame["holding_cost_rate_annual"] / 365.0).sum())
    orders = len(purchase_orders)
    ordering = float(sum(order_cost_by_supplier[s] for s in purchase_orders["supplier_id"]))
    lost_sales_cost = float((frame["lost_sales"] * frame["unit_price"]).sum())
    cogs = float((frame["fulfilled"] * frame["unit_cost"]).sum())
    stockout_days = int((frame["lost_sales"] > 0).sum())

    def ratio(numerator: float, denominator: float) -> float | None:
        return numerator / denominator if denominator > 0 else None

    turnover = ratio(cogs, avg_on_hand_value)
    metrics = [
        # Demand and service
        Metric(metric_id="demand_total", value=demand, unit="units"),
        Metric(metric_id="fulfilled_units", value=fulfilled, unit="units"),
        Metric(metric_id="lost_sales_units", value=lost, unit="units"),
        Metric(metric_id="fill_rate", value=ratio(fulfilled, demand), unit="ratio"),
        Metric(metric_id="stockout_days", value=float(stockout_days), unit="item-days"),
        Metric(
            metric_id="stockout_day_rate", value=ratio(stockout_days, n_items * t), unit="ratio"
        ),
        # Stock
        Metric(
            metric_id="avg_on_hand_units",
            value=float(frame["closing_on_hand"].sum()) / t,
            unit="units",
        ),
        Metric(metric_id="avg_on_hand_value", value=avg_on_hand_value, unit="USD"),
        Metric(
            metric_id="inventory_turnover",
            value=turnover * 365.0 / t if turnover is not None else None,
            unit="turns per year",
        ),
        # Ordering volume
        Metric(metric_id="purchase_orders", value=float(orders), unit="orders"),
        Metric(
            metric_id="units_ordered",
            value=float(purchase_orders["quantity"].sum()) if orders else 0.0,
            unit="units",
        ),
        Metric(
            metric_id="order_frequency",
            value=ratio(orders, n_items * t / 7.0),
            unit="orders per item per week",
        ),
        # Cost components
        Metric(metric_id="ordering_cost", value=ordering, unit="USD"),
        Metric(metric_id="holding_cost", value=holding, unit="USD"),
        Metric(metric_id="inventory_cost", value=ordering + holding, unit="USD"),
        Metric(metric_id="lost_sales_cost", value=lost_sales_cost, unit="USD"),
        Metric(metric_id="total_cost", value=ordering + holding + lost_sales_cost, unit="USD"),
    ]
    for product, rows in frame.groupby("product_id", sort=True):
        metrics.append(
            Metric(
                metric_id="fill_rate",
                value=ratio(float(rows["fulfilled"].sum()), float(rows["demand"].sum())),
                unit="ratio",
                scope=f"product:{product}",
            )
        )
    return tuple(metrics)
