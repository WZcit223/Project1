"""Shared builders for foundation tests: a tiny retail-like sales table and product table."""

from datetime import UTC, datetime

import pandas as pd

from industrial_ai.foundation.datasets import (
    Dataset,
    DatasetSchema,
    DType,
    FieldSpec,
    ForeignKey,
    SourceInfo,
    SourceType,
    build_dataset,
)
from industrial_ai.foundation.provenance import Lineage, TransformationStep

FIXED_TIME = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)

SALES_SCHEMA = DatasetSchema(
    schema_id="test.sales",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="date", dtype=DType.DATE),
        FieldSpec(name="product_id", dtype=DType.STR),
        FieldSpec(name="quantity", dtype=DType.INT, min=0, unit="units"),
        FieldSpec(name="unit_price", dtype=DType.FLOAT, min=0.01, nullable=True),
        FieldSpec(name="channel", dtype=DType.CATEGORY, allowed_values=("store", "online")),
    ),
    primary_key=("date", "product_id"),
    foreign_keys=(
        ForeignKey(
            fields=("product_id",), ref_schema_id="test.product", ref_fields=("product_id",)
        ),
    ),
    time_index="date",
    entity_keys=("product_id",),
)

PRODUCT_SCHEMA = DatasetSchema(
    schema_id="test.product",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="product_id", dtype=DType.STR),
        FieldSpec(name="is_food", dtype=DType.BOOL),
    ),
    primary_key=("product_id",),
)

SOURCE = SourceInfo(name="test sales", source_type=SourceType.FIXTURE, tags=("test",))
LINEAGE = Lineage(transformations=(TransformationStep(step="handwritten"),))


def sales_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2016-01-01", "2016-01-01", "2016-01-02", "2016-01-02"]),
            "product_id": ["A", "B", "A", "B"],
            "quantity": pd.Series([3, 0, 5, 1], dtype="int64"),
            "unit_price": [1.25, 2.5, None, 2.5],
            "channel": pd.Categorical(["store", "online", "store", "store"]),
        }
    )


def product_frame() -> pd.DataFrame:
    return pd.DataFrame({"product_id": ["A", "B"], "is_food": [True, False]})


def make_sales(data: pd.DataFrame | None = None, version: str = "1") -> Dataset:
    return build_dataset(
        dataset_id="sales",
        version=version,
        schema=SALES_SCHEMA,
        data=sales_frame() if data is None else data,
        source=SOURCE,
        lineage=LINEAGE,
        created_at=FIXED_TIME,
    )


def make_products(data: pd.DataFrame | None = None) -> Dataset:
    return build_dataset(
        dataset_id="products",
        version="1",
        schema=PRODUCT_SCHEMA,
        data=product_frame() if data is None else data,
        source=SOURCE,
        lineage=Lineage(),
        created_at=FIXED_TIME,
    )
