"""Tests for industrial_ai.foundation.datasets."""

import dataclasses

import pandas as pd
import pytest
from pydantic import ValidationError

from industrial_ai.core.errors import DatasetError
from industrial_ai.foundation.datasets import (
    DatasetBundle,
    DatasetSchema,
    DType,
    FieldSpec,
    ForeignKey,
)
from industrial_ai.foundation.provenance import content_hash

from .builders import FIXED_TIME, SALES_SCHEMA, SOURCE, make_products, make_sales, sales_frame

# --- schema -----------------------------------------------------------------------------------


def test_schema_json_round_trip() -> None:
    assert DatasetSchema.model_validate_json(SALES_SCHEMA.model_dump_json()) == SALES_SCHEMA


def test_schema_field_lookup() -> None:
    assert SALES_SCHEMA.field("quantity").dtype is DType.INT
    assert SALES_SCHEMA.field_names[0] == "date"
    with pytest.raises(KeyError):
        SALES_SCHEMA.field("missing")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fields": ()},
        {"schema_version": "1.0"},
        {"primary_key": ("nope",)},
        {"time_index": "nope"},
        {"entity_keys": ("nope",)},
        {"fields": (FieldSpec(name="a", dtype=DType.INT), FieldSpec(name="a", dtype=DType.INT))},
        {"foreign_keys": (ForeignKey(fields=("nope",), ref_schema_id="x", ref_fields=("id",)),)},
    ],
    ids=["no-fields", "bad-version", "pk", "time-index", "entity", "duplicate", "fk"],
)
def test_invalid_schemas_are_rejected(kwargs: dict[str, object]) -> None:
    base: dict[str, object] = {
        "schema_id": "s",
        "schema_version": "1.0.0",
        "fields": (FieldSpec(name="a", dtype=DType.INT),),
    }
    with pytest.raises(ValidationError):
        DatasetSchema.model_validate(base | kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "Bad Name", "dtype": "int"},
        {"name": "x", "dtype": "int", "min": 5, "max": 1},
        {"name": "x", "dtype": "str", "min": 0},
        {"name": "x", "dtype": "complex"},
    ],
)
def test_invalid_field_specs_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        FieldSpec.model_validate(kwargs)


def test_foreign_key_arity_must_match() -> None:
    with pytest.raises(ValidationError):
        ForeignKey(fields=("a", "b"), ref_schema_id="x", ref_fields=("a",))


# --- build_dataset ----------------------------------------------------------------------------


def test_build_computes_metadata_and_provenance() -> None:
    dataset = make_sales()
    meta, prov = dataset.metadata, dataset.provenance
    assert meta.row_count == 4
    assert meta.content_hash == content_hash(sales_frame())
    assert meta.entity_counts == {"product_id": 2}
    assert meta.time_range is not None
    assert meta.time_range.start.date().isoformat() == "2016-01-01"
    assert meta.time_range.end.date().isoformat() == "2016-01-02"
    assert meta.created_at == FIXED_TIME and meta.name == SOURCE.name
    assert prov.artifact_id == "sales@1"
    assert prov.output.content_hash == meta.content_hash
    assert prov.transformations[0].step == "handwritten"
    assert dataset.as_input().content_hash == meta.content_hash


def test_build_reorders_columns_and_resets_index() -> None:
    shuffled = sales_frame().iloc[:, ::-1].set_axis([7, 8, 9, 10])
    dataset = make_sales(shuffled)
    assert tuple(dataset.data.columns) == SALES_SCHEMA.field_names
    assert list(dataset.data.index) == [0, 1, 2, 3]
    assert dataset.metadata.content_hash == make_sales().metadata.content_hash


@pytest.mark.parametrize(
    "frame",
    [sales_frame().drop(columns="channel"), sales_frame().assign(extra=1)],
    ids=["missing", "extra"],
)
def test_build_rejects_column_mismatch(frame: pd.DataFrame) -> None:
    with pytest.raises(DatasetError, match="columns do not match"):
        make_sales(frame)


def test_dataset_rejects_inconsistent_metadata() -> None:
    dataset = make_sales()
    tampered = dataset.data.assign(quantity=[9, 9, 9, 9])
    with pytest.raises(DatasetError, match="content hash"):
        dataclasses.replace(dataset, data=tampered)
    with pytest.raises(DatasetError, match="row_count"):
        dataclasses.replace(dataset, data=dataset.data.iloc[:2])


def test_empty_dataset_has_no_time_range() -> None:
    empty = make_sales(sales_frame().iloc[0:0])
    assert empty.metadata.row_count == 0 and empty.metadata.time_range is None


# --- bundle -----------------------------------------------------------------------------------


def test_bundle_lookup_and_hash() -> None:
    bundle = DatasetBundle(
        "retail", "1", {"sales": make_sales(), "products": make_products()}, SOURCE
    )
    assert bundle.table("sales").dataset_id == "sales"
    assert bundle.by_schema("test.product").dataset_id == "products"
    reordered = DatasetBundle(
        "retail", "1", {"products": make_products(), "sales": make_sales()}, SOURCE
    )
    assert bundle.content_hash == reordered.content_hash
    with pytest.raises(DatasetError, match="no table"):
        bundle.table("missing")
    with pytest.raises(DatasetError, match="0 tables"):
        bundle.by_schema("missing")


def test_bundle_requires_tables() -> None:
    with pytest.raises(DatasetError):
        DatasetBundle("empty", "1", {}, SOURCE)
