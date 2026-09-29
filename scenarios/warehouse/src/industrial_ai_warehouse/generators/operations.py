"""Synthetic warehouse operations from canonical retail reference data (TASK-WH-001).

Pipeline (each ``ops.*`` table through the framework's Synthetic Data Engine; ``derived.*`` tables
are deterministic summaries with provenance)::

    retail.price  → derived.product_price ─┐
    retail.sales  → derived.store_demand ──┼─► ops.warehouse (rule_based)
                                           │   ops.supplier (rule_based)
                                           │   ops.supplier_lead_time (statistical)
                                           └─► ops.product_supplier (rule_based)
    sales + warehouse + product_supplier + lead times → derived.planning_input
                                           ──► ops.initial_inventory (rule_based)
                                           ──► ops.replenishment_policy (rule_based)
"""

from datetime import datetime

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from industrial_ai.foundation.datasets import Dataset, DatasetBundle, SourceInfo, SourceType
from industrial_ai.foundation.provenance import ComponentRef, Lineage
from industrial_ai.foundation.validation import ConstraintSet, RelationConstraint
from industrial_ai.synthetic import GenerationRequest, GenerationSize, SyntheticEngine
from industrial_ai.synthetic.generators import builtin_registry
from industrial_ai_warehouse.generators._support import (
    derived_dataset,
    mean_daily_demand,
    table_seed,
)
from industrial_ai_warehouse.schemas.operations import (
    INITIAL_INVENTORY,
    PLANNING_INPUT,
    PRODUCT_PRICE,
    PRODUCT_SUPPLIER,
    REPLENISHMENT_POLICY,
    STORE_DEMAND,
    SUPPLIER,
    SUPPLIER_LEAD_TIME,
    WAREHOUSE,
)

OPERATIONS_COMPONENT = ComponentRef(id="warehouse.operations", version="1.0.0")


class OperationsConfig(BaseModel):
    """Assumptions of the synthetic operational environment (all explicit, all recorded)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    supplier_count: int = Field(default=5, ge=1)
    order_cost_range: tuple[float, float] = (20.0, 60.0)
    min_order_qty_choices: tuple[int, ...] = (0, 6, 12)
    lead_time_gamma_shape: float = Field(default=9.0, gt=0)
    lead_time_gamma_scale: float = Field(default=0.7, gt=0)
    """Supplier mean lead time ~ Gamma(shape, scale) days (mean 6.3), at least 2 days."""
    lead_time_std_range: tuple[float, float] = (0.5, 2.0)
    lead_time_mean_std_correlation: float = Field(default=0.5, ge=-0.99, le=0.99)
    on_time_probability_range: tuple[float, float] = (0.85, 0.99)
    cost_ratio: float = Field(default=0.7, gt=0, le=1)
    """unit_cost = mean selling price × cost_ratio."""
    case_pack_choices: tuple[int, ...] = (6, 12, 24)
    holding_cost_rate_annual: float = Field(default=0.25, ge=0, le=1)
    capacity_days_of_demand: float = Field(default=60.0, gt=0)
    demand_window_days: int = Field(default=365, ge=28)
    review_period_days: int = Field(default=1, ge=1)
    order_cycle_days: int = Field(default=14, ge=1)
    target_service_level: float = Field(default=0.95, ge=0.5, le=0.9999)


def generate_operations(
    retail: DatasetBundle,
    seed: int,
    config: OperationsConfig | None = None,
    engine: SyntheticEngine | None = None,
    created_at: datetime | None = None,
) -> DatasetBundle:
    """Generate the synthetic operations bundle for a canonical retail bundle (reproducible)."""
    cfg = config or OperationsConfig()
    engine = engine or SyntheticEngine(builtin_registry())
    prefix = f"{retail.bundle_id}.ops.s{seed}"
    sales, price = retail.table("sales"), retail.table("price")

    def gen(
        table: str,
        schema_generator: str,
        schema: object,
        parameters: dict[str, JsonValue],
        reference: Dataset | None = None,
        rows: int | None = None,
        constraints: ConstraintSet | None = None,
    ) -> Dataset:
        return engine.generate(
            GenerationRequest.model_validate(
                {
                    "generator_id": schema_generator,
                    "dataset_id": f"{prefix}.{table}",
                    "output_schema": schema,
                    "constraints": constraints or ConstraintSet(),
                    "seed": table_seed(seed, table),
                    "size": GenerationSize(rows=rows),
                    "parameters": parameters,
                    "tags": ("synthetic", "warehouse", "operations"),
                }
            ),
            reference=reference,
            created_at=created_at,
        )

    demand = mean_daily_demand(sales.data, cfg.demand_window_days)
    product_price = derived_dataset(
        dataset_id=f"{prefix}.product_price",
        schema=PRODUCT_PRICE,
        frame=_mean_price(price.data),
        inputs=[price],
        step="mean_price_per_product",
        details={},
        created_at=created_at,
    )
    store_demand = derived_dataset(
        dataset_id=f"{prefix}.store_demand",
        schema=STORE_DEMAND,
        frame=demand.groupby("store_id", as_index=False).agg(
            mean_daily_demand=("mean_daily_demand", "sum")
        ),
        inputs=[sales],
        step="sum_mean_daily_demand_per_store",
        details={"window_days": cfg.demand_window_days, "leading_zeros_excluded": True},
        created_at=created_at,
    )
    warehouse = gen(
        "warehouse",
        "rule_based",
        WAREHOUSE,
        {
            "columns": {
                "warehouse_id": {"kind": "sequence", "prefix": "WH", "width": 2},
                "store_id": {"kind": "reference_column", "column": "store_id"},
                "capacity_units": {
                    "kind": "linear",
                    "source": "mean_daily_demand",
                    "scale": cfg.capacity_days_of_demand,
                    "offset": 1,
                    "integer": True,
                },
                "holding_cost_rate_annual": {
                    "kind": "constant",
                    "value": cfg.holding_cost_rate_annual,
                },
            }
        },
        reference=store_demand,
    )
    supplier = gen(
        "supplier",
        "rule_based",
        SUPPLIER,
        {
            "columns": {
                "supplier_id": {"kind": "sequence", "prefix": "SUP", "width": 3},
                "order_cost": {
                    "kind": "uniform",
                    "low": cfg.order_cost_range[0],
                    "high": cfg.order_cost_range[1],
                    "decimals": 2,
                },
                "min_order_qty": {"kind": "choice", "values": list(cfg.min_order_qty_choices)},
            }
        },
        rows=cfg.supplier_count,
    )
    lead_time = gen(
        "supplier_lead_time",
        "statistical",
        SUPPLIER_LEAD_TIME,
        {
            "copy_from_reference": ["supplier_id"],
            "columns": {
                "lead_time_mean_days": {
                    "kind": "gamma",
                    "shape": cfg.lead_time_gamma_shape,
                    "scale": cfg.lead_time_gamma_scale,
                    "clip_min": max(2.0, cfg.lead_time_std_range[1]),
                    "decimals": 2,
                },
                "lead_time_std_days": {
                    "kind": "uniform",
                    "low": cfg.lead_time_std_range[0],
                    "high": cfg.lead_time_std_range[1],
                    "decimals": 2,
                },
                "on_time_probability": {
                    "kind": "uniform",
                    "low": cfg.on_time_probability_range[0],
                    "high": cfg.on_time_probability_range[1],
                    "decimals": 3,
                },
            },
            "correlation": {
                "columns": ["lead_time_mean_days", "lead_time_std_days"],
                "matrix": [
                    [1.0, cfg.lead_time_mean_std_correlation],
                    [cfg.lead_time_mean_std_correlation, 1.0],
                ],
            },
        },
        reference=supplier,
        constraints=ConstraintSet(
            constraints=(
                RelationConstraint(left="lead_time_std_days", op="<=", right="lead_time_mean_days"),
            )
        ),
    )
    product_supplier = gen(
        "product_supplier",
        "rule_based",
        PRODUCT_SUPPLIER,
        {
            "columns": {
                "product_id": {"kind": "reference_column", "column": "product_id"},
                "supplier_id": {"kind": "choice", "values": supplier.data["supplier_id"].tolist()},
                "unit_cost": {
                    "kind": "linear",
                    "source": "avg_unit_price",
                    "scale": cfg.cost_ratio,
                    "decimals": 2,
                },
                "case_pack": {"kind": "choice", "values": list(cfg.case_pack_choices)},
            }
        },
        reference=product_price,
    )
    planning = derived_dataset(
        dataset_id=f"{prefix}.planning_input",
        schema=PLANNING_INPUT,
        frame=_planning_input(demand, warehouse.data, product_supplier.data, lead_time.data, cfg),
        inputs=[sales, warehouse, product_supplier, lead_time],
        step="join_planning_inputs",
        details={
            "initial_stock_target": (
                "mean_daily_demand * (lead_time_mean_days + order_cycle_days / 2)"
            ),
            "order_cycle_days": cfg.order_cycle_days,
            "window_days": cfg.demand_window_days,
        },
        created_at=created_at,
    )
    initial_inventory = gen(
        "initial_inventory",
        "rule_based",
        INITIAL_INVENTORY,
        {
            "columns": {
                "product_id": {"kind": "reference_column", "column": "product_id"},
                "warehouse_id": {"kind": "reference_column", "column": "warehouse_id"},
                "on_hand_units": {
                    "kind": "linear",
                    "source": "initial_stock_target",
                    "integer": True,
                },
                "on_order_units": {"kind": "constant", "value": 0},
            }
        },
        reference=planning,
    )
    policy = gen(
        "replenishment_policy",
        "rule_based",
        REPLENISHMENT_POLICY,
        {
            "columns": {
                "product_id": {"kind": "reference_column", "column": "product_id"},
                "warehouse_id": {"kind": "reference_column", "column": "warehouse_id"},
                "review_period_days": {"kind": "constant", "value": cfg.review_period_days},
                "order_cycle_days": {"kind": "constant", "value": cfg.order_cycle_days},
                "target_service_level": {"kind": "constant", "value": cfg.target_service_level},
            }
        },
        reference=planning,
    )
    tables = {
        "product_price": product_price,
        "store_demand": store_demand,
        "warehouse": warehouse,
        "supplier": supplier,
        "supplier_lead_time": lead_time,
        "product_supplier": product_supplier,
        "planning_input": planning,
        "initial_inventory": initial_inventory,
        "replenishment_policy": policy,
    }
    return DatasetBundle(
        bundle_id=prefix,
        version="1",
        tables=tables,
        source=SourceInfo(
            name=f"Synthetic warehouse operations for {retail.bundle_id} (seed {seed})",
            source_type=SourceType.SYNTHETIC,
            tags=("synthetic", "warehouse", "operations"),
        ),
        lineage=Lineage(
            inputs=tuple(retail.tables[n].as_input() for n in sorted(retail.tables)),
            component=OPERATIONS_COMPONENT,
            parameters={"config": cfg.model_dump(mode="json")},
            seed=seed,
        ),
    )


def build_hybrid_bundle(retail: DatasetBundle, operations: DatasetBundle) -> DatasetBundle:
    """Real reference tables + synthetic operations: the Hybrid Validation Environment."""
    overlap = sorted(set(retail.tables) & set(operations.tables))
    if overlap:
        raise ValueError(f"table names overlap: {overlap}")
    return DatasetBundle(
        bundle_id=f"{operations.bundle_id}.hybrid",
        version="1",
        tables={**retail.tables, **operations.tables},
        source=SourceInfo(
            name=f"Hybrid validation environment: {retail.bundle_id} + {operations.bundle_id}",
            source_type=SourceType.DERIVED,
            tags=("hybrid", "warehouse"),
        ),
        lineage=Lineage(
            inputs=tuple(
                bundle.tables[name].as_input()
                for bundle in (retail, operations)
                for name in sorted(bundle.tables)
            ),
            component=OPERATIONS_COMPONENT,
        ),
    )


def _mean_price(prices: pd.DataFrame) -> pd.DataFrame:
    means = prices.groupby("product_id")["unit_price"].mean().round(4)
    return pd.DataFrame({"product_id": means.index, "avg_unit_price": means.to_numpy()})


def _planning_input(
    demand: pd.DataFrame,
    warehouse: pd.DataFrame,
    product_supplier: pd.DataFrame,
    lead_time: pd.DataFrame,
    cfg: OperationsConfig,
) -> pd.DataFrame:
    frame = (
        demand.merge(warehouse[["warehouse_id", "store_id"]], on="store_id", validate="many_to_one")
        .merge(
            product_supplier[["product_id", "supplier_id"]], on="product_id", validate="many_to_one"
        )
        .merge(
            lead_time[["supplier_id", "lead_time_mean_days"]],
            on="supplier_id",
            validate="many_to_one",
        )
    )
    frame["initial_stock_target"] = (
        frame["mean_daily_demand"] * (frame["lead_time_mean_days"] + cfg.order_cycle_days / 2)
    ).round(6)
    return (
        frame.drop(columns="supplier_id")
        .sort_values(["product_id", "warehouse_id"])
        .reset_index(drop=True)
    )
