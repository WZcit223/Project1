"""Canonical retail-demand model, schema version 1.0.0 (docs/data-model.md §2).

These schemas are the Warehouse pack's view of demand-side reference data. The framework never
sees M5 column names: the M5 adapter converts raw files into these tables.
"""

from industrial_ai.foundation.datasets import DatasetSchema, DType, FieldSpec, ForeignKey

SCHEMA_VERSION = "1.0.0"


def _fk(field: str, ref_schema_id: str, ref_field: str | None = None) -> ForeignKey:
    return ForeignKey(
        fields=(field,), ref_schema_id=ref_schema_id, ref_fields=(ref_field or field,)
    )


REGION = DatasetSchema(
    schema_id="retail.region",
    schema_version=SCHEMA_VERSION,
    fields=(
        FieldSpec(name="region_id", dtype=DType.STR, description="Region code, e.g. CA"),
        FieldSpec(name="name", dtype=DType.STR, description="Region name, e.g. California"),
    ),
    primary_key=("region_id",),
)

STORE = DatasetSchema(
    schema_id="retail.store",
    schema_version=SCHEMA_VERSION,
    fields=(
        FieldSpec(name="store_id", dtype=DType.STR),
        FieldSpec(name="region_id", dtype=DType.STR),
    ),
    primary_key=("store_id",),
    foreign_keys=(_fk("region_id", "retail.region"),),
)

CATEGORY = DatasetSchema(
    schema_id="retail.category",
    schema_version=SCHEMA_VERSION,
    fields=(FieldSpec(name="category_id", dtype=DType.STR, description="e.g. FOODS"),),
    primary_key=("category_id",),
)

DEPARTMENT = DatasetSchema(
    schema_id="retail.department",
    schema_version=SCHEMA_VERSION,
    fields=(
        FieldSpec(name="department_id", dtype=DType.STR, description="e.g. FOODS_3"),
        FieldSpec(name="category_id", dtype=DType.STR),
    ),
    primary_key=("department_id",),
    foreign_keys=(_fk("category_id", "retail.category"),),
)

PRODUCT = DatasetSchema(
    schema_id="retail.product",
    schema_version=SCHEMA_VERSION,
    fields=(
        FieldSpec(name="product_id", dtype=DType.STR),
        FieldSpec(name="department_id", dtype=DType.STR),
        FieldSpec(name="category_id", dtype=DType.STR),
    ),
    primary_key=("product_id",),
    foreign_keys=(
        _fk("department_id", "retail.department"),
        _fk("category_id", "retail.category"),
    ),
)

CALENDAR = DatasetSchema(
    schema_id="retail.calendar",
    schema_version=SCHEMA_VERSION,
    fields=(
        FieldSpec(name="date", dtype=DType.DATE),
        FieldSpec(name="week_id", dtype=DType.INT, description="Retail week number"),
        FieldSpec(name="weekday", dtype=DType.INT, min=1, max=7, description="ISO: 1=Mon … 7=Sun"),
        FieldSpec(name="month", dtype=DType.INT, min=1, max=12),
        FieldSpec(name="year", dtype=DType.INT),
    ),
    primary_key=("date",),
    time_index="date",
)

CALENDAR_EVENT = DatasetSchema(
    schema_id="retail.calendar_event",
    schema_version=SCHEMA_VERSION,
    fields=(
        FieldSpec(name="date", dtype=DType.DATE),
        FieldSpec(name="event_name", dtype=DType.STR),
        FieldSpec(
            name="event_type",
            dtype=DType.CATEGORY,
            allowed_values=("Cultural", "National", "Religious", "Sporting"),
        ),
    ),
    primary_key=("date", "event_name"),
    foreign_keys=(_fk("date", "retail.calendar"),),
    time_index="date",
)

CALENDAR_SNAP = DatasetSchema(
    schema_id="retail.calendar_snap",
    schema_version=SCHEMA_VERSION,
    fields=(
        FieldSpec(name="date", dtype=DType.DATE),
        FieldSpec(name="region_id", dtype=DType.STR),
        FieldSpec(
            name="snap_active",
            dtype=DType.BOOL,
            description="SNAP food-assistance purchases allowed in the region on this date",
        ),
    ),
    primary_key=("date", "region_id"),
    foreign_keys=(_fk("date", "retail.calendar"), _fk("region_id", "retail.region")),
    time_index="date",
    entity_keys=("region_id",),
)

SALES = DatasetSchema(
    schema_id="retail.sales",
    schema_version=SCHEMA_VERSION,
    fields=(
        FieldSpec(name="date", dtype=DType.DATE),
        FieldSpec(name="product_id", dtype=DType.STR),
        FieldSpec(name="store_id", dtype=DType.STR),
        FieldSpec(
            name="quantity",
            dtype=DType.INT,
            min=0,
            unit="units",
            description="Observed daily unit sales (demand reference; censored by stockouts)",
        ),
    ),
    primary_key=("date", "product_id", "store_id"),
    foreign_keys=(
        _fk("date", "retail.calendar"),
        _fk("product_id", "retail.product"),
        _fk("store_id", "retail.store"),
    ),
    time_index="date",
    entity_keys=("product_id", "store_id"),
)

PRICE = DatasetSchema(
    schema_id="retail.price",
    schema_version=SCHEMA_VERSION,
    fields=(
        FieldSpec(name="week_id", dtype=DType.INT),
        FieldSpec(name="product_id", dtype=DType.STR),
        FieldSpec(name="store_id", dtype=DType.STR),
        FieldSpec(name="unit_price", dtype=DType.FLOAT, min=0.01, unit="USD"),
    ),
    primary_key=("week_id", "product_id", "store_id"),
    foreign_keys=(_fk("product_id", "retail.product"), _fk("store_id", "retail.store")),
    entity_keys=("product_id", "store_id"),
)

RETAIL_SCHEMAS: dict[str, DatasetSchema] = {
    "region": REGION,
    "store": STORE,
    "category": CATEGORY,
    "department": DEPARTMENT,
    "product": PRODUCT,
    "calendar": CALENDAR,
    "calendar_event": CALENDAR_EVENT,
    "calendar_snap": CALENDAR_SNAP,
    "sales": SALES,
    "price": PRICE,
}
"""Canonical tables by bundle table name."""
