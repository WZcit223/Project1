"""Inventory simulation plugin ``inventory_simulation`` 1.0.0 (docs/scenario-spec.md §5).

Daily, per item (product × warehouse), single echelon, lost sales. For each day ``t``:

1. **Receive** shipments arriving on ``t``.
2. **Serve demand**: fulfilled = min(on hand, demand); the rest is lost (not back-ordered).
3. **Review** (every ``review_period_days``): the strategy returns a quantity; the simulation rounds
   it up to the case pack and the supplier's minimum order quantity.
4. **Order**: lead time ``max(1, round(mean + delta_t + std · z_t))`` plus, with probability
   ``1 − on_time_probability``, an extra 1–``max_extra_delay_days`` days. In a supply disruption
   window the supplier ships ``ceil(quantity · supply_capacity_factor)``; the shortfall is lost.

Random draws (``z_t``, lateness, delay) are pre-sampled per item and day from the run seed, so all
strategies compared with the same seed face identical supply conditions (common random numbers).
"""

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from industrial_ai.core.errors import SimulationInputError
from industrial_ai.foundation.datasets import Dataset, DatasetBundle
from industrial_ai.foundation.validation import ConstraintSet
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.simulation import OutputTable, PluginKind, PluginOutput, RunContext
from industrial_ai_warehouse.schemas.simulation import INVENTORY_LEDGER, PURCHASE_ORDER
from industrial_ai_warehouse.simulation.metrics import inventory_metrics
from industrial_ai_warehouse.strategies.base import (
    DailyObservation,
    ForecastView,
    ItemContext,
    ItemPolicy,
    ReplenishmentStrategy,
    StrategyRegistry,
)

REQUIRED_INPUTS = (
    "ops.synthetic_demand",
    "ops.initial_inventory",
    "ops.replenishment_policy",
    "ops.product_supplier",
    "ops.supplier",
    "ops.supplier_lead_time",
    "ops.warehouse",
    "derived.product_price",
    "retail.sales",
)
SUPPLY_PARAMETERS = frozenset(
    {
        "lead_time_delta",
        "disruption_start_day",
        "disruption_duration_days",
        "supply_capacity_factor",
        "planner_aware",
    }
)
LEDGER_COUNTS = (
    "opening_on_hand",
    "arrivals",
    "demand",
    "fulfilled",
    "lost_sales",
    "closing_on_hand",
    "on_order",
    "inventory_position",
    "order_qty",
)


class InventorySimulationParameters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_id: str
    strategy_version: str | None = None
    strategy_parameters: dict[str, JsonValue] = Field(default_factory=dict)
    forecast_upstream: str = "forecast"
    """Name of the upstream forecast result (required when the strategy uses forecasts)."""
    history_window_days: int = Field(default=365, ge=28)
    max_extra_delay_days: int = Field(default=3, ge=1)


class SupplyEffects(BaseModel):
    """Scenario supply parameters (docs/scenario-spec.md §3); absent ones keep their defaults."""

    model_config = ConfigDict(frozen=True)

    lead_time_delta: int = Field(default=0, ge=-30, le=60)
    disruption_start_day: int = Field(default=0, ge=0)
    disruption_duration_days: int = Field(default=0, ge=0)
    """0 = the lead-time delta and capacity factor apply to the whole horizon."""
    supply_capacity_factor: float = Field(default=1.0, ge=0, le=1)
    planner_aware: bool = False

    def in_window(self, day: int) -> bool:
        if self.disruption_duration_days == 0:
            return True
        end = self.disruption_start_day + self.disruption_duration_days
        return self.disruption_start_day <= day < end


@dataclass
class _Item:
    product_id: str
    warehouse_id: str
    supplier_id: str
    demand: np.ndarray
    on_hand: int
    case_pack: int
    min_order_qty: int
    lead_mean: float
    lead_std: float
    on_time_probability: float
    review_period: int
    policy: ItemPolicy
    on_order: int = 0
    pipeline: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class _Order:
    product_id: str
    warehouse_id: str
    supplier_id: str
    order_day: int
    quantity: int
    shipped: int
    lead_time: int


class InventorySimulationPlugin:
    plugin_id = "inventory_simulation"
    plugin_version = "1.0.0"
    kind = PluginKind.SIMULATION
    description = (
        "Daily single-echelon inventory with lost sales, sampled lead times and a pluggable "
        "replenishment strategy."
    )
    parameter_model: type[BaseModel] = InventorySimulationParameters
    required_inputs: tuple[str, ...] = REQUIRED_INPUTS

    def __init__(self, strategies: StrategyRegistry) -> None:
        self._strategies = strategies

    def run(
        self,
        dataset: Dataset | DatasetBundle,
        scenario: ScenarioSpec | None,
        parameters: BaseModel,
        constraints: ConstraintSet,
        context: RunContext,
    ) -> PluginOutput:
        assert isinstance(parameters, InventorySimulationParameters)
        if not isinstance(dataset, DatasetBundle):
            raise SimulationInputError("inventory_simulation needs the hybrid bundle")
        p = parameters
        strategy = self._strategies.get(p.strategy_id, p.strategy_version)
        try:
            strategy_params = strategy.parameter_model.model_validate(p.strategy_parameters)
        except ValidationError as exc:
            raise SimulationInputError(
                f"invalid parameters for strategy {p.strategy_id}: {exc}"
            ) from exc
        supply, applied = _supply_effects(scenario)
        dates = pd.date_range(context.start_date, context.end_date, freq="D")
        tables = {schema_id: dataset.by_schema(schema_id).data for schema_id in REQUIRED_INPUTS}
        forecasts = _forecasts(context, p, strategy.uses_forecast)
        items = _items(tables, dates, supply, strategy, strategy_params, forecasts, p)

        children = np.random.SeedSequence(context.seed).spawn(len(items))
        ledgers, orders = [], []
        for item, child in zip(items, children, strict=True):
            rng = np.random.default_rng(child)
            ledger, item_orders = _simulate(item, dates, supply, rng, p.max_extra_delay_days)
            ledgers.append(ledger)
            orders.extend(item_orders)
        ledger = (
            pd.concat(ledgers, ignore_index=True)
            .sort_values(["date", "product_id", "warehouse_id"], kind="stable")
            .reset_index(drop=True)
        )
        purchase_orders = _purchase_orders(orders, dates)
        suppliers = tables["ops.supplier"]
        order_costs = {
            str(s): float(c)
            for s, c in zip(suppliers["supplier_id"], suppliers["order_cost"], strict=True)
        }
        return PluginOutput(
            tables={
                "inventory_ledger": OutputTable(INVENTORY_LEDGER, ledger),
                "purchase_order": OutputTable(PURCHASE_ORDER, purchase_orders),
            },
            metrics=inventory_metrics(
                ledger, purchase_orders, _item_costs(tables, items), order_costs, len(dates)
            ),
            warnings=_capacity_warnings(ledger, tables["ops.warehouse"]),
            applied_scenario_parameters=applied,
            details={
                "strategy": {"id": strategy.strategy_id, "version": strategy.strategy_version},
                "strategy_parameters": strategy_params.model_dump(mode="json"),
                "supply_effects": supply.model_dump(mode="json"),
                "items": len(items),
                "horizon_days": len(dates),
            },
        )


def _supply_effects(scenario: ScenarioSpec | None) -> tuple[SupplyEffects, frozenset[str]]:
    if scenario is None:
        return SupplyEffects(), frozenset()
    present = {k: v for k, v in scenario.parameters.items() if k in SUPPLY_PARAMETERS}
    try:
        return SupplyEffects.model_validate(present), frozenset(present)
    except ValidationError as exc:
        raise SimulationInputError(f"invalid supply scenario parameters: {exc}") from exc


def _forecasts(
    context: RunContext, p: InventorySimulationParameters, needed: bool
) -> pd.DataFrame | None:
    if p.forecast_upstream not in context.upstream:
        if needed:
            raise SimulationInputError(
                f"strategy {p.strategy_id} needs the upstream forecast {p.forecast_upstream!r}"
            )
        return None
    prediction = context.upstream[p.forecast_upstream].prediction
    if prediction is None:
        raise SimulationInputError(f"upstream {p.forecast_upstream!r} has no prediction table")
    missing = {"product_id", "store_id"} - set(prediction.data.columns)
    if missing:
        raise SimulationInputError(f"forecast lacks entity columns {sorted(missing)}")
    return prediction.data


def _lookup(frame: pd.DataFrame, key: str, value: str) -> dict[str, object]:
    return {str(k): v for k, v in zip(frame[key], frame[value], strict=True)}


def _items(
    tables: dict[str, pd.DataFrame],
    dates: pd.DatetimeIndex,
    supply: SupplyEffects,
    strategy: ReplenishmentStrategy,
    strategy_params: BaseModel,
    forecasts: pd.DataFrame | None,
    p: InventorySimulationParameters,
) -> list[_Item]:
    store_of = _lookup(tables["ops.warehouse"], "warehouse_id", "store_id")
    product_supplier = tables["ops.product_supplier"]
    supplier_of = _lookup(product_supplier, "product_id", "supplier_id")
    case_pack_of = _lookup(product_supplier, "product_id", "case_pack")
    lead = tables["ops.supplier_lead_time"]
    lead_mean_of = _lookup(lead, "supplier_id", "lead_time_mean_days")
    lead_std_of = _lookup(lead, "supplier_id", "lead_time_std_days")
    on_time_of = _lookup(lead, "supplier_id", "on_time_probability")
    moq_of = _lookup(tables["ops.supplier"], "supplier_id", "min_order_qty")
    policy = tables["ops.replenishment_policy"]
    settings = {
        (str(prod), str(wh)): (int(review), int(cycle), float(service))
        for prod, wh, review, cycle, service in zip(
            policy["product_id"],
            policy["warehouse_id"],
            policy["review_period_days"],
            policy["order_cycle_days"],
            policy["target_service_level"],
            strict=True,
        )
    }
    demand = _daily(tables["ops.synthetic_demand"])
    sales = _daily(tables["retail.sales"])
    history = sales[sales["date"] < dates[0]]

    items = []
    inventory = tables["ops.initial_inventory"].sort_values(["product_id", "warehouse_id"])
    for product, warehouse, on_hand, on_order in zip(
        inventory["product_id"].astype(str),
        inventory["warehouse_id"].astype(str),
        inventory["on_hand_units"].astype(int),
        inventory["on_order_units"].astype(int),
        strict=True,
    ):
        store = str(store_of[warehouse])
        supplier = str(supplier_of[product])
        lead_mean = float(str(lead_mean_of[supplier]))
        lead_std = float(str(lead_std_of[supplier]))
        review_period, order_cycle, service_level = settings[(product, warehouse)]
        view = None
        if forecasts is not None:
            view = ForecastView(
                forecasts[(forecasts["product_id"] == product) & (forecasts["store_id"] == store)]
            )
        item_context = ItemContext(
            product_id=product,
            warehouse_id=warehouse,
            history=_active_history(history, product, store, p.history_window_days),
            lead_time_mean_days=lead_mean + (supply.lead_time_delta if supply.planner_aware else 0),
            lead_time_std_days=lead_std,
            review_period_days=review_period,
            order_cycle_days=order_cycle,
            target_service_level=service_level,
            forecast=view,
        )
        item = _Item(
            product_id=product,
            warehouse_id=warehouse,
            supplier_id=supplier,
            demand=_horizon_demand(demand, product, store, dates),
            on_hand=int(on_hand),
            case_pack=int(str(case_pack_of[product])),
            min_order_qty=int(str(moq_of[supplier])),
            lead_mean=lead_mean,
            lead_std=lead_std,
            on_time_probability=float(str(on_time_of[supplier])),
            review_period=review_period,
            policy=strategy.create_policy(item_context, strategy_params),
        )
        if on_order > 0:  # initial pipeline arrives after the mean lead time
            item.pipeline[max(1, round(lead_mean))] = int(on_order)
            item.on_order = int(on_order)
        items.append(item)
    return items


def _daily(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"])
    return result


def _horizon_demand(
    demand: pd.DataFrame, product: str, store: str, dates: pd.DatetimeIndex
) -> np.ndarray:
    rows = demand[(demand["product_id"] == product) & (demand["store_id"] == store)]
    series = rows.set_index("date")["quantity"].reindex(dates)
    if series.isna().any():
        raise SimulationInputError(
            f"synthetic demand for {product}/{store} does not cover the horizon "
            f"({int(series.isna().sum())} missing days)"
        )
    values: np.ndarray = series.to_numpy(dtype="int64")
    return values


def _active_history(sales: pd.DataFrame, product: str, store: str, window: int) -> np.ndarray:
    rows = sales[(sales["product_id"] == product) & (sales["store_id"] == store)].sort_values(
        "date"
    )
    sold = rows.loc[rows["quantity"] > 0, "date"]
    if sold.empty:
        return np.zeros(0)
    start = max(sold.min(), rows["date"].max() - pd.Timedelta(days=window - 1))
    values: np.ndarray = rows.loc[rows["date"] >= start, "quantity"].to_numpy(dtype="float64")
    return values


def _simulate(
    item: _Item,
    dates: pd.DatetimeIndex,
    supply: SupplyEffects,
    rng: np.random.Generator,
    max_delay: int,
) -> tuple[pd.DataFrame, list[_Order]]:
    horizon = len(dates)
    z = rng.standard_normal(horizon)
    late = rng.random(horizon) >= item.on_time_probability
    delay = rng.integers(1, max_delay, endpoint=True, size=horizon)
    rows: list[tuple[int, ...]] = []
    orders: list[_Order] = []
    for t in range(horizon):
        arrivals = item.pipeline.pop(t, 0)
        item.on_hand += arrivals
        item.on_order -= arrivals
        opening = item.on_hand
        demand = int(item.demand[t])
        fulfilled = min(item.on_hand, demand)
        item.on_hand -= fulfilled
        order_qty = 0
        if t % item.review_period == 0:
            observation = DailyObservation(
                day_index=t,
                date=dates[t].date(),
                on_hand=item.on_hand,
                on_order=item.on_order,
                demand=demand,
                fulfilled=fulfilled,
            )
            order_qty = _rounded(item.policy.order_quantity(observation), item)
        if order_qty > 0:
            in_window = supply.in_window(t)
            delta = supply.lead_time_delta if in_window else 0
            lead_time = max(1, round(item.lead_mean + delta + item.lead_std * float(z[t])))
            if late[t]:
                lead_time += int(delay[t])
            factor = supply.supply_capacity_factor if in_window else 1.0
            shipped = math.ceil(order_qty * factor)
            if shipped > 0:
                item.pipeline[t + lead_time] = item.pipeline.get(t + lead_time, 0) + shipped
                item.on_order += shipped
            orders.append(
                _Order(
                    item.product_id,
                    item.warehouse_id,
                    item.supplier_id,
                    t,
                    order_qty,
                    shipped,
                    lead_time,
                )
            )
        rows.append(
            (
                opening,
                arrivals,
                demand,
                fulfilled,
                demand - fulfilled,
                item.on_hand,
                item.on_order,
                item.on_hand + item.on_order,
                order_qty,
            )
        )
    frame = pd.DataFrame(rows, columns=list(LEDGER_COUNTS), dtype="int64")
    frame.insert(0, "date", dates)
    frame.insert(1, "product_id", item.product_id)
    frame.insert(2, "warehouse_id", item.warehouse_id)
    return frame, orders


def _rounded(raw: float, item: _Item) -> int:
    if raw <= 0:
        return 0
    quantity = max(raw, float(item.min_order_qty))
    return int(math.ceil(quantity / item.case_pack) * item.case_pack)


def _purchase_orders(orders: list[_Order], dates: pd.DatetimeIndex) -> pd.DataFrame:
    horizon = len(dates)
    rows = []
    for o in orders:
        order_date = dates[o.order_day]
        arrival_date = order_date + pd.Timedelta(days=o.lead_time)
        received: pd.Timestamp | None = arrival_date
        if o.shipped == 0:
            status, received = "not_shipped", None
        elif o.order_day + o.lead_time >= horizon:
            status, received = "open", None
        elif o.shipped < o.quantity:
            status = "partially_received"
        else:
            status = "received"
        rows.append(
            {
                "po_id": f"{o.product_id}.{o.warehouse_id}.d{o.order_day:04d}",
                "product_id": o.product_id,
                "warehouse_id": o.warehouse_id,
                "supplier_id": o.supplier_id,
                "order_date": order_date,
                "quantity": o.quantity,
                "shipped_qty": o.shipped,
                "sampled_lead_time_days": o.lead_time,
                "expected_arrival_date": arrival_date,
                "received_date": received,
                "status": status,
            }
        )
    frame = pd.DataFrame(rows, columns=list(PURCHASE_ORDER.field_names))
    for column in ("order_date", "expected_arrival_date", "received_date"):
        frame[column] = pd.to_datetime(frame[column])
    return frame.astype(
        {"quantity": "int64", "shipped_qty": "int64", "sampled_lead_time_days": "int64"}
    )


def _item_costs(tables: dict[str, pd.DataFrame], items: list[_Item]) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "product_id": [i.product_id for i in items],
            "warehouse_id": [i.warehouse_id for i in items],
        }
    )
    frame = frame.merge(
        tables["ops.product_supplier"][["product_id", "unit_cost"]], on="product_id"
    )
    prices = tables["derived.product_price"].rename(columns={"avg_unit_price": "unit_price"})
    frame = frame.merge(prices, on="product_id")
    warehouses = tables["ops.warehouse"][["warehouse_id", "holding_cost_rate_annual"]]
    return frame.merge(warehouses, on="warehouse_id")


def _capacity_warnings(ledger: pd.DataFrame, warehouses: pd.DataFrame) -> tuple[str, ...]:
    stock = ledger.groupby(["warehouse_id", "date"], as_index=False).agg(
        closing_on_hand=("closing_on_hand", "sum")
    )
    stock = stock.merge(warehouses[["warehouse_id", "capacity_units"]], on="warehouse_id")
    over = int((stock["closing_on_hand"] > stock["capacity_units"]).sum())
    if over == 0:
        return ()
    return (f"warehouse capacity exceeded on {over} warehouse-days (reported, not enforced)",)
