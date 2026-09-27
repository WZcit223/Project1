"""Tests for industrial_ai.foundation.ingestion."""

from pathlib import Path

import pytest

from industrial_ai.core.errors import DuplicatePluginError, IngestionError
from industrial_ai.foundation.datasets import DatasetBundle, DType
from industrial_ai.foundation.ingestion import (
    LOADER_ID,
    DatasetAdapter,
    load_table,
    new_adapter_registry,
)
from industrial_ai.foundation.provenance import file_hash
from industrial_ai.foundation.validation import validate_dataset

from .builders import PRODUCT_SCHEMA, SALES_SCHEMA, SOURCE, make_products, make_sales

SALES_CSV = """date,product_id,quantity,unit_price,channel
2016-01-01,A,3,1.25,store
2016-01-01,B,0,2.5,online
2016-01-02,A,5,,store
2016-01-02,B,1,2.5,store
"""


def write(tmp_path: Path, text: str, name: str = "sales.csv") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def load_sales(path: Path) -> object:
    return load_table(path, SALES_SCHEMA, dataset_id="sales", version="1", source=SOURCE)


def test_csv_is_loaded_with_schema_types(tmp_path: Path) -> None:
    path = write(tmp_path, SALES_CSV)
    dataset = load_table(path, SALES_SCHEMA, dataset_id="sales", version="1", source=SOURCE)
    assert validate_dataset(dataset).passed
    assert str(dataset.data["quantity"].dtype) == "int64"
    assert dataset.metadata.content_hash == make_sales().metadata.content_hash
    step = dataset.provenance.transformations[0]
    assert dataset.provenance.component is not None
    assert dataset.provenance.component.id == LOADER_ID
    assert step.step == "ingest"
    assert step.details["file_hash"] == file_hash(path.read_bytes())
    assert step.details["file"] == "sales.csv"  # file name only, no machine-specific path


def test_nullable_int_and_bool_columns(tmp_path: Path) -> None:
    path = write(tmp_path, "product_id,is_food\nA,true\nB,No\n", "products.csv")
    products = load_table(path, PRODUCT_SCHEMA, dataset_id="products", version="1", source=SOURCE)
    assert products.data["is_food"].tolist() == [True, False]
    assert products.metadata.content_hash == make_products().metadata.content_hash


def test_parquet_is_loaded(tmp_path: Path) -> None:
    path = tmp_path / "sales.parquet"
    make_sales().data.to_parquet(path, index=False)
    dataset = load_table(path, SALES_SCHEMA, dataset_id="sales", version="1", source=SOURCE)
    assert dataset.metadata.content_hash == make_sales().metadata.content_hash


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (SALES_CSV.replace(",channel", "").replace(",store", "").replace(",online", ""), "missing"),
        (SALES_CSV.replace("channel\n", "channel,extra\n"), "unexpected"),
        (SALES_CSV.replace("2016-01-01,A,3", "2016-01-01,A,three"), "'quantity'"),
        (SALES_CSV.replace("2016-01-01,A,3", "2016-01-01,A,3.5"), "'quantity'"),
        (SALES_CSV.replace("2016-01-02,A,5", "2016-13-45,A,5"), "'date'"),
    ],
    ids=["missing-column", "extra-column", "non-numeric", "non-integral", "bad-date"],
)
def test_bad_files_raise_ingestion_error(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(IngestionError, match=message):
        load_sales(write(tmp_path, text))


def test_bad_bool_is_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, "product_id,is_food\nA,maybe\n", "p.csv")
    with pytest.raises(IngestionError, match="not valid bool"):
        load_table(path, PRODUCT_SCHEMA, dataset_id="p", version="1", source=SOURCE)


def test_unsupported_format_and_missing_file(tmp_path: Path) -> None:
    with pytest.raises(IngestionError, match="unsupported format"):
        load_sales(write(tmp_path, "x", "sales.xlsx"))
    with pytest.raises(IngestionError, match="cannot read"):
        load_sales(tmp_path / "absent.csv")


def test_range_violations_are_left_to_validation(tmp_path: Path) -> None:
    dataset = load_table(
        write(tmp_path, SALES_CSV.replace("B,0,", "B,-4,")),
        SALES_SCHEMA,
        dataset_id="sales",
        version="1",
        source=SOURCE,
    )
    assert not validate_dataset(dataset).passed
    assert SALES_SCHEMA.field("quantity").dtype is DType.INT


class FakeAdapter:
    adapter_id = "fake"
    adapter_version = "1.0.0"
    description = "Test adapter returning a fixed bundle."

    def load(self, source: Path) -> DatasetBundle:
        return DatasetBundle("fake", "1", {"sales": make_sales()}, SOURCE)


def test_adapter_protocol_and_registry(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    assert isinstance(adapter, DatasetAdapter)
    registry = new_adapter_registry()
    registry.register(adapter)
    assert registry.get("fake").load(tmp_path).table("sales").dataset_id == "sales"
    with pytest.raises(DuplicatePluginError):
        registry.register(FakeAdapter())
