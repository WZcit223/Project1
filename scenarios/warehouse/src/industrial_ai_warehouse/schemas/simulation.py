"""Inventory simulation output schemas, version 1.0.0 (docs/data-model.md §4).

Run and strategy are identified by the output dataset id (``<run_id>.<plugin>.<table>``), so they
are not repeated as columns.
"""

from industrial_ai.foundation.datasets import DatasetSchema, DType, FieldSpec

SCHEMA_VERSION = "1.0.0"

INVENTORY_LEDGER = DatasetSchema(
    schema_id="sim.inventory_ledger",
    schema_version=SCHEMA_VERSION,
    fields=(
        FieldSpec(name="date", dtype=DType.DATE),
        FieldSpec(name="product_id", dtype=DType.STR),
        FieldSpec(name="warehouse_id", dtype=DType.STR),
        FieldSpec(name="opening_on_hand", dtype=DType.INT, min=0, unit="units"),
        FieldSpec(name="arrivals", dtype=DType.INT, min=0, unit="units"),
        FieldSpec(name="demand", dtype=DType.INT, min=0, unit="units"),
        FieldSpec(name="fulfilled", dtype=DType.INT, min=0, unit="units"),
        FieldSpec(name="lost_sales", dtype=DType.INT, min=0, unit="units"),
        FieldSpec(name="closing_on_hand", dtype=DType.INT, min=0, unit="units"),
        FieldSpec(name="on_order", dtype=DType.INT, min=0, unit="units"),
        FieldSpec(name="inventory_position", dtype=DType.INT, min=0, unit="units"),
        FieldSpec(name="order_qty", dtype=DType.INT, min=0, unit="units"),
    ),
    primary_key=("date", "product_id", "warehouse_id"),
    time_index="date",
    entity_keys=("product_id", "warehouse_id"),
    description="Daily inventory accounting per item: receive → serve demand (lost sales) → order.",
)

PURCHASE_ORDER = DatasetSchema(
    schema_id="sim.purchase_order",
    schema_version=SCHEMA_VERSION,
    fields=(
        FieldSpec(name="po_id", dtype=DType.STR),
        FieldSpec(name="product_id", dtype=DType.STR),
        FieldSpec(name="warehouse_id", dtype=DType.STR),
        FieldSpec(name="supplier_id", dtype=DType.STR),
        FieldSpec(name="order_date", dtype=DType.DATE),
        FieldSpec(name="quantity", dtype=DType.INT, min=1, unit="units"),
        FieldSpec(name="shipped_qty", dtype=DType.INT, min=0, unit="units"),
        FieldSpec(name="sampled_lead_time_days", dtype=DType.INT, min=1, unit="days"),
        FieldSpec(name="expected_arrival_date", dtype=DType.DATE),
        FieldSpec(name="received_date", dtype=DType.DATE, nullable=True),
        FieldSpec(
            name="status",
            dtype=DType.STR,
            allowed_values=("received", "partially_received", "open", "not_shipped"),
        ),
    ),
    primary_key=("po_id",),
    description=(
        "Purchase orders placed in the horizon; shipped_qty < quantity under a supply-capacity "
        "limit (the shortfall is not back-ordered)."
    ),
)
