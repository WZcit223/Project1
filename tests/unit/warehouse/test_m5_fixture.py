"""The committed M5-shaped fixture is synthetic, reproducible and in the M5 layout."""

import filecmp
from pathlib import Path

import pandas as pd

from industrial_ai.foundation.datasets import SourceType
from industrial_ai_warehouse.adapters.m5.fixture import FIXTURE_DAYS, write_m5_fixture
from industrial_ai_warehouse.adapters.m5.source import M5Source

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "m5_like"


def test_regeneration_is_byte_identical(tmp_path: Path) -> None:
    write_m5_fixture(tmp_path)
    committed = sorted(p.name for p in FIXTURE_DIR.iterdir())
    assert committed == sorted(p.name for p in tmp_path.iterdir())
    match, mismatch, errors = filecmp.cmpfiles(FIXTURE_DIR, tmp_path, committed, shallow=False)
    assert not mismatch and not errors, (mismatch, errors)


def test_fixture_is_labelled_synthetic() -> None:
    source = M5Source.read(FIXTURE_DIR)
    assert source is not None
    assert source.source_type is SourceType.FIXTURE
    assert "not real M5" in source.source


def test_fixture_uses_m5_layout() -> None:
    calendar = pd.read_csv(FIXTURE_DIR / "calendar.csv")
    sales = pd.read_csv(FIXTURE_DIR / "sales_train_evaluation.csv")
    assert list(sales.columns[:6]) == ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    assert list(sales.columns[6:]) == list(calendar["d"])
    assert len(calendar) == FIXTURE_DAYS
    assert calendar.loc[0, "weekday"] == "Saturday" and calendar.loc[0, "wday"] == 1
