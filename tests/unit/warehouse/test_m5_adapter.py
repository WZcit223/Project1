"""Tests for the M5 adapter (Gate 3: M5 → canonical), run on the synthetic fixture."""

import shutil
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from industrial_ai.core.errors import IngestionError
from industrial_ai.foundation.datasets import DatasetBundle, SourceType
from industrial_ai.foundation.ingestion import DatasetAdapter, new_adapter_registry
from industrial_ai.foundation.validation import validate_bundle
from industrial_ai_warehouse.adapters.m5 import M5Adapter
from industrial_ai_warehouse.schemas import RETAIL_SCHEMAS

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "m5_like"


@pytest.fixture(scope="module")
def bundle() -> DatasetBundle:
    return M5Adapter().load(FIXTURE_DIR)


def copy_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "m5"
    shutil.copytree(FIXTURE_DIR, target)
    return target


def test_all_canonical_tables_are_produced_and_valid(bundle: DatasetBundle) -> None:
    assert set(bundle.tables) == set(RETAIL_SCHEMAS)
    report = validate_bundle(bundle)
    assert report.passed, report.failures
    assert not report.skipped  # every foreign key could be checked inside the bundle


def test_row_counts(bundle: DatasetBundle) -> None:
    raw = pd.read_csv(FIXTURE_DIR / "sales_train_evaluation.csv")
    days = sum(c.startswith("d_") for c in raw.columns)
    assert bundle.table("sales").metadata.row_count == len(raw) * days
    assert bundle.table("product").metadata.row_count == raw["item_id"].nunique()
    assert bundle.table("store").metadata.row_count == raw["store_id"].nunique()
    assert bundle.table("calendar_snap").metadata.row_count == days * 2  # two regions


def test_sales_values_are_preserved(bundle: DatasetBundle) -> None:
    raw = pd.read_csv(FIXTURE_DIR / "sales_train_evaluation.csv")
    sales = bundle.table("sales").data
    assert int(sales["quantity"].sum()) == int(raw.filter(like="d_").to_numpy().sum())
    first = raw.iloc[0]
    row = sales[
        (sales["product_id"] == first["item_id"])
        & (sales["store_id"] == first["store_id"])
        & (sales["date"] == pd.Timestamp("2011-01-30"))
    ]
    assert int(row["quantity"].iloc[0]) == int(first["d_2"])


def test_weekday_is_iso(bundle: DatasetBundle) -> None:
    calendar = bundle.table("calendar").data
    first = calendar.iloc[0]
    assert first["date"] == pd.Timestamp("2011-01-29") and first["weekday"] == 6  # Saturday


def test_events_include_second_event_column(bundle: DatasetBundle) -> None:
    events = bundle.table("calendar_event").data
    christmas_2012 = events[events["date"] == pd.Timestamp("2012-12-25")]
    assert set(christmas_2012["event_name"]) == {"Christmas", "OrthodoxChristmasTest"}


def test_attribution_and_provenance(bundle: DatasetBundle) -> None:
    sales = bundle.table("sales")
    assert sales.dataset_id == "m5_fixture.sales"
    assert sales.metadata.source_type is SourceType.FIXTURE
    prov = sales.provenance
    assert prov.component is not None and prov.component.id == "m5"
    steps = [s.step for s in prov.transformations]
    assert steps == ["ingest", "unpivot_daily_sales"]
    files = prov.transformations[0].details["files"]
    assert isinstance(files, dict) and "sales_train_evaluation.csv" in files


def test_conversion_is_deterministic(bundle: DatasetBundle) -> None:
    assert M5Adapter().load(FIXTURE_DIR).content_hash == bundle.content_hash


def test_validation_file_is_used_when_evaluation_is_absent(tmp_path: Path) -> None:
    source = copy_fixture(tmp_path)
    (source / "sales_train_evaluation.csv").rename(source / "sales_train_validation.csv")
    loaded = M5Adapter().load(source)
    assert loaded.table("sales").provenance.transformations[0].details["sales_file"] == (
        "sales_train_validation.csv"
    )


def test_missing_source_json_defaults_to_reference(tmp_path: Path) -> None:
    source = copy_fixture(tmp_path)
    (source / "SOURCE.json").unlink()
    loaded = M5Adapter().load(source)
    assert loaded.bundle_id == "m5"
    assert loaded.table("sales").metadata.source_type is SourceType.REFERENCE
    assert "unknown" in loaded.source.description


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: (d / "sell_prices.csv").unlink(), "missing sell_prices.csv"),
        (lambda d: (d / "sales_train_evaluation.csv").unlink(), "missing sales file"),
        (
            lambda d: (
                pd.read_csv(d / "calendar.csv")
                .assign(wday=1)
                .to_csv(d / "calendar.csv", index=False)
            ),
            "'wday' does not match",
        ),
        (
            lambda d: (
                pd.read_csv(d / "calendar.csv")
                .drop(columns="snap_TX")
                .to_csv(d / "calendar.csv", index=False)
            ),
            "snap_TX",
        ),
        (
            lambda d: (
                pd.read_csv(d / "calendar.csv").iloc[:-5].to_csv(d / "calendar.csv", index=False)
            ),
            "sales days not in",
        ),
    ],
    ids=["no-prices", "no-sales", "bad-wday", "no-snap-column", "short-calendar"],
)
def test_invalid_inputs_raise(
    tmp_path: Path, mutate: Callable[[Path], object], message: str
) -> None:
    source = copy_fixture(tmp_path)
    mutate(source)
    with pytest.raises(IngestionError, match=message):
        M5Adapter().load(source)


def test_adapter_satisfies_protocol_and_registers() -> None:
    adapter = M5Adapter()
    assert isinstance(adapter, DatasetAdapter)
    registry = new_adapter_registry()
    registry.register(adapter)
    assert ("m5", "1.0.0") in registry
