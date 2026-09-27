"""Inventory KPIs exactly as defined in docs/data-model.md §6.

Notation per item i and day t: demand D, fulfilled F, lost L = D − F, closing on-hand I, unit
cost c, unit price p, annual holding rate h, order cost k, horizon T days, N items. Undefined
ratios are ``None``, never a substitute number.
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
    avg_inventory_value = float(value.sum()) / t
    holding = float((value * frame["holding_cost_rate_annual"] / 365.0).sum())
    orders = len(purchase_orders)
    ordering = float(sum(order_cost_by_supplier[s] for s in purchase_orders["supplier_id"]))
    cogs = float((frame["fulfilled"] * frame["unit_cost"]).sum())
    stockout_days = int((frame["lost_sales"] > 0).sum())

    def ratio(numerator: float, denominator: float) -> float | None:
        return numerator / denominator if denominator > 0 else None

    turnover = ratio(cogs, avg_inventory_value)
    metrics = [
        Metric(metric_id="demand_total", value=demand, unit="units"),
        Metric(metric_id="service_level", value=ratio(fulfilled, demand), unit="ratio"),
        Metric(metric_id="stockout_rate", value=ratio(stockout_days, n_items * t), unit="ratio"),
        Metric(metric_id="lost_sales_units", value=lost, unit="units"),
        Metric(
            metric_id="lost_sales_value",
            value=float((frame["lost_sales"] * frame["unit_price"]).sum()),
            unit="USD",
        ),
        Metric(
            metric_id="avg_inventory_units",
            value=float(frame["closing_on_hand"].sum()) / t,
            unit="units",
        ),
        Metric(metric_id="avg_inventory_value", value=avg_inventory_value, unit="USD"),
        Metric(metric_id="holding_cost", value=holding, unit="USD"),
        Metric(metric_id="ordering_cost", value=ordering, unit="USD"),
        Metric(metric_id="inventory_cost", value=holding + ordering, unit="USD"),
        Metric(
            metric_id="order_frequency",
            value=ratio(orders, n_items * t / 7.0),
            unit="orders per item per week",
        ),
        Metric(
            metric_id="inventory_turnover",
            value=turnover * 365.0 / t if turnover is not None else None,
            unit="turns per year",
        ),
    ]
    for product, rows in frame.groupby("product_id", sort=True):
        metrics.append(
            Metric(
                metric_id="service_level",
                value=ratio(float(rows["fulfilled"].sum()), float(rows["demand"].sum())),
                unit="ratio",
                scope=f"product:{product}",
            )
        )
    return tuple(metrics)
