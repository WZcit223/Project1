"""Helpers of scripts/validation_report.py: counts come from pytest, statistics are computed."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validation_report.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validation_report", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" errors="0" failures="1" skipped="1" tests="4" time="2.5">
<testcase classname="tests.unit.test_a" name="test_one" time="0.1"/>
<testcase classname="tests.unit.test_a" name="test_two" time="0.1"><failure message="x"/></testcase>
<testcase classname="tests.ui.test_b" name="test_three" time="0.1"><skipped message="y"/></testcase>
<testcase classname="tests.ui.test_b" name="test_four" time="0.1"/>
</testsuite></testsuites>"""


def test_junit_summary_uses_pytest_counts(tmp_path: Path) -> None:
    path = tmp_path / "junit.xml"
    path.write_text(JUNIT, encoding="utf-8")
    result = load().summarise_junit("V1", "title", "scope", "uv run pytest tests", path)
    assert (result.tests, result.failures, result.skipped, result.passed) == (4, 1, 1, 2)
    assert not result.ok
    assert result.per_module == {"tests/ui/test_b.py": 2, "tests/unit/test_a.py": 2}
    assert result.failed == ["tests/unit/test_a.py::test_two"]


def test_demand_statistics() -> None:
    days = pd.date_range("2024-01-01", periods=14, freq="D")  # Monday start, two full weeks
    frame = pd.DataFrame(
        {
            "date": list(days) * 2,
            "product_id": ["A"] * 14 + ["B"] * 14,
            "store_id": ["S"] * 28,
            "quantity": [2] * 14 + [0, 4] * 7,
        }
    )
    stats = load().demand_stats(frame)
    assert (stats.series, stats.days) == (2, 14)
    assert stats.mean_per_series_day == pytest.approx(2.0)
    assert stats.zero_share == pytest.approx(0.25)
    assert len(stats.weekday_index) == 7
    assert sum(stats.weekday_index) / 7 == pytest.approx(1.0, abs=0.01)


def test_formatting() -> None:
    fmt = load().fmt
    assert fmt(None) == "–"
    assert fmt(0.1234, "pct") == "12.3%"
    assert fmt(12345.6, "usd") == "$12,346"
