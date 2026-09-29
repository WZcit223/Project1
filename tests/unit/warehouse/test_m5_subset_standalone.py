"""The standalone subset script produces the same files as the project version."""

import importlib.util
import json
from datetime import date
from pathlib import Path
from types import ModuleType

from industrial_ai_warehouse.adapters.m5 import M5Adapter, M5Source, SubsetFilters
from industrial_ai_warehouse.adapters.m5.subset import make_subset

REPO = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO / "tests" / "fixtures" / "m5_like"


def load_standalone() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "m5_subset_standalone", REPO / "scripts" / "m5_subset_standalone.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_standalone_matches_project_version(tmp_path: Path) -> None:
    standalone = load_standalone()
    standalone.make_subset(
        FIXTURE_DIR, tmp_path / "a", ["CA_1"], ["FOODS_3"], [], 3, date(2026, 9, 20)
    )
    make_subset(
        FIXTURE_DIR,
        tmp_path / "b",
        SubsetFilters(stores=("CA_1",), departments=("FOODS_3",), top_n=3),
        download_date=date(2026, 9, 20),
    )
    for name in ("calendar.csv", "sell_prices.csv", "sales_train_evaluation.csv"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name

    a = json.loads((tmp_path / "a" / "SOURCE.json").read_text())
    b = json.loads((tmp_path / "b" / "SOURCE.json").read_text())
    assert {k: v for k, v in a.items() if k != "created_at"} == {
        k: v for k, v in b.items() if k != "created_at"
    }
    assert M5Source.read(tmp_path / "a") is not None  # valid for the project model
    assert M5Adapter().load(tmp_path / "a").bundle_id == "m5_subset_ca_1_foods_3_top3"
