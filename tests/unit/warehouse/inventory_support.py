"""A minimal hybrid bundle and test strategies for inventory simulation tests."""

from datetime import date, timedelta

import pandas as pd
from pydantic import BaseModel, Field

from industrial_ai.foundation.datasets import (
    DatasetBundle,
    DatasetSchema,
    SourceInfo,
    SourceType,
    build_dataset,
)
from industrial_ai.foundation.provenance import Lineage
from industrial_ai.simulation import RunContext, SimulationEngine, new_simulation_registry
from industrial_ai_warehouse.schemas import OPERATIONS_SCHEMAS, RETAIL_SCHEMAS, SYNTHETIC_DEMAND
from industrial_ai_warehouse.simulation import InventorySimulationPlugin
from industrial_ai_warehouse.strategies import (
    DailyObservation,
    ItemContext,
    ItemPolicy,
    new_strategy_registry,
)

START = date(2016, 1, 1)
SOURCE = SourceInfo(name="test", source_type=SourceType.FIXTURE)


class OrderUpToParams(BaseModel):
    level: int = Field(ge=0)


class _OrderUpTo:
    def __init__(self, level: int) -> None:
        self.level = level

    def order_quantity(self, observation: DailyObservation) -> float:
        return float(max(0, self.level - observation.inventory_position))


class OrderUpToStrategy:
    """Order up to a fixed level every review day (tests only)."""

    strategy_id = "test_order_up_to"
    strategy_version = "1.0.0"
    description = "Order up to a fixed level (tests only)."
    parameter_model: type[BaseModel] = OrderUpToParams
    uses_forecast = False
    seen: list[ItemContext] = []

    def create_policy(self, item: ItemContext, parameters: BaseModel) -> ItemPolicy:
        assert isinstance(parameters, OrderUpToParams)
        OrderUpToStrategy.seen.append(item)
        return _OrderUpTo(parameters.level)


class NeedsForecastStrategy(OrderUpToStrategy):
    strategy_id = "test_needs_forecast"
    uses_forecast = True


def table(name: str, schema: DatasetSchema, rows: list[dict[str, object]]) -> object:
    return build_dataset(
        dataset_id=f"t.{name}",
        version="1",
        schema=schema,
        data=pd.DataFrame(rows, columns=list(schema.field_names)),
        source=SOURCE,
        lineage=Lineage(),
    )


def bundle(
    demand: list[int],
    *,
    on_hand: int = 10,
    lead_mean: float = 2.0,
    lead_std: float = 0.0,
    on_time: float = 1.0,
    case_pack: int = 1,
    moq: int = 0,
    review: int = 1,
    capacity: int = 1000,
) -> DatasetBundle:
    ops = OPERATIONS_SCHEMAS
    dates = [START + timedelta(days=i) for i in range(len(demand))]
    history = [START - timedelta(days=i) for i in range(60, 0, -1)]
    tables = {
        "synthetic_demand": table(
            "synthetic_demand",
            SYNTHETIC_DEMAND,
            [
                {
                    "date": pd.Timestamp(d),
                    "product_id": "P1",
                    "store_id": "S1",
                    "quantity": q,
                    "scenario_id": "none",
                }
                for d, q in zip(dates, demand, strict=True)
            ],
        ),
        "initial_inventory": table(
            "initial_inventory",
            ops["initial_inventory"],
            [
                {
                    "product_id": "P1",
                    "warehouse_id": "WH01",
                    "on_hand_units": on_hand,
                    "on_order_units": 0,
                }
            ],
        ),
        "replenishment_policy": table(
            "replenishment_policy",
            ops["replenishment_policy"],
            [
                {
                    "product_id": "P1",
                    "warehouse_id": "WH01",
                    "review_period_days": review,
                    "order_cycle_days": 14,
                    "target_service_level": 0.95,
                }
            ],
        ),
        "product_supplier": table(
            "product_supplier",
            ops["product_supplier"],
            [
                {
                    "product_id": "P1",
                    "supplier_id": "SUP001",
                    "unit_cost": 1.0,
                    "case_pack": case_pack,
                }
            ],
        ),
        "supplier": table(
            "supplier",
            ops["supplier"],
            [{"supplier_id": "SUP001", "order_cost": 10.0, "min_order_qty": moq}],
        ),
        "supplier_lead_time": table(
            "supplier_lead_time",
            ops["supplier_lead_time"],
            [
                {
                    "supplier_id": "SUP001",
                    "lead_time_mean_days": lead_mean,
                    "lead_time_std_days": lead_std,
                    "on_time_probability": on_time,
                }
            ],
        ),
        "warehouse": table(
            "warehouse",
            ops["warehouse"],
            [
                {
                    "warehouse_id": "WH01",
                    "store_id": "S1",
                    "capacity_units": capacity,
                    "holding_cost_rate_annual": 0.365,
                }
            ],
        ),
        "product_price": table(
            "product_price", ops["product_price"], [{"product_id": "P1", "avg_unit_price": 2.0}]
        ),
        "sales": table(
            "sales",
            RETAIL_SCHEMAS["sales"],
            [
                {"date": pd.Timestamp(d), "product_id": "P1", "store_id": "S1", "quantity": 3}
                for d in history
            ],
        ),
    }
    return DatasetBundle("t", "1", tables, SOURCE)  # type: ignore[arg-type]


def engine() -> SimulationEngine:
    strategies = new_strategy_registry()
    strategies.register(OrderUpToStrategy())
    strategies.register(NeedsForecastStrategy())
    registry = new_simulation_registry()
    registry.register(InventorySimulationPlugin(strategies))
    return SimulationEngine(registry)


def context(days: int, seed: int = 1) -> RunContext:
    return RunContext(
        run_id="inv", seed=seed, start_date=START, end_date=START + timedelta(days=days - 1)
    )
