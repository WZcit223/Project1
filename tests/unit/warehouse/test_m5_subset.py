"""Tests for M5 subset extraction (run on the synthetic fixture with tiny chunks)."""

import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from industrial_ai.core.errors import IngestionError
from industrial_ai.foundation.datasets import SourceType
from industrial_ai.foundation.validation import validate_bundle
from industrial_ai_warehouse.adapters.m5 import M5Adapter, M5Source, SubsetFilters
from industrial_ai_warehouse.adapters.m5.subset import default_dataset_id, make_subset

REPO = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO / "tests" / "fixtures" / "m5_like"
FILTERS = SubsetFilters(stores=("CA_1",), departments=("FOODS_3",), top_n=3)


def test_subset_keeps_top_items_of_selected_store_and_department(tmp_path: Path) -> None:
    record = make_subset(
        FIXTURE_DIR, tmp_path, FILTERS, download_date=date(2026, 9, 20), chunksize=5
    )
    sales = pd.read_csv(tmp_path / "sales_train_evaluation.csv")
    assert set(sales["store_id"]) == {"CA_1"} and set(sales["dept_id"]) == {"FOODS_3"}
    assert len(sales) == 3

    full = pd.read_csv(FIXTURE_DIR / "sales_train_evaluation.csv")
    candidates = full[(full["store_id"] == "CA_1") & (full["dept_id"] == "FOODS_3")]
    totals = candidates.set_index("item_id").filter(like="d_").sum(axis=1)
    assert set(sales["item_id"]) == set(totals.sort_values(ascending=False).index[:3])

    prices = pd.read_csv(tmp_path / "sell_prices.csv")
    assert set(zip(prices["item_id"], prices["store_id"], strict=True)) == set(
        zip(sales["item_id"], sales["store_id"], strict=True)
    )
    assert (tmp_path / "calendar.csv").read_bytes() == (FIXTURE_DIR / "calendar.csv").read_bytes()

    assert record.dataset_id == "m5_subset_ca_1_foods_3_top3"
    assert record.source_type is SourceType.REFERENCE
    assert record.download_date == date(2026, 9, 20)
    assert set(record.source_files) == {
        "calendar.csv",
        "sell_prices.csv",
        "sales_train_evaluation.csv",
    }
    assert M5Source.read(tmp_path) == record


def test_values_are_copied_verbatim(tmp_path: Path) -> None:
    make_subset(FIXTURE_DIR, tmp_path, FILTERS, chunksize=7)
    original = {line for line in (FIXTURE_DIR / "sell_prices.csv").read_text().splitlines()}
    subset = (tmp_path / "sell_prices.csv").read_text().splitlines()
    assert subset[0] == "store_id,item_id,wm_yr_wk,sell_price"
    assert set(subset[1:]) <= original


def test_subset_converts_and_validates(tmp_path: Path) -> None:
    make_subset(FIXTURE_DIR, tmp_path, FILTERS)
    bundle = M5Adapter().load(tmp_path)
    assert bundle.bundle_id == "m5_subset_ca_1_foods_3_top3"
    assert bundle.table("product").metadata.row_count == 3
    report = validate_bundle(bundle)
    assert report.passed and not report.skipped


def test_no_match_and_missing_files_raise(tmp_path: Path) -> None:
    with pytest.raises(IngestionError, match="no M5 series match"):
        make_subset(FIXTURE_DIR, tmp_path, SubsetFilters(stores=("WI_9",)))
    with pytest.raises(IngestionError, match="missing sales file"):
        make_subset(tmp_path, tmp_path / "out", FILTERS)


def test_default_dataset_id() -> None:
    assert default_dataset_id(SubsetFilters(categories=("FOODS",))) == "m5_subset_foods"


def test_cli_uses_documented_defaults(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "make_m5_subset.py"),
            "--input",
            str(FIXTURE_DIR),
            "--output",
            str(tmp_path),
            "--top-n",
            "2",
            "--download-date",
            "2026-09-20",
        ],
        check=True,
        capture_output=True,
    )
    record = M5Source.read(tmp_path)
    assert record is not None
    assert record.filters == SubsetFilters(stores=("CA_1",), departments=("FOODS_3",), top_n=2)
