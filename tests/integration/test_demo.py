"""The scripted demo (scripts/demo.py) and the demo guide stay consistent with the evidence.

- The CLI runs the Golden Path through the Application API and reproduces its output (fixture).
- On the committed M5 subset, the demo reproduces the Golden Path numbers of the committed
  validation report, and the demo guide's expected-output table equals the report (no drift).
"""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "m5_like"
REFERENCE = ROOT / "data" / "reference" / "m5_subset"
ROW = re.compile(r"^\| (baseline|high_demand) \| (\w+) \| ([\d.]+%) \|(?:.*?\|)? (\$[\d,]+) \|$")


def load_demo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("demo", ROOT / "scripts" / "demo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rows(path: Path) -> dict[tuple[str, str], tuple[str, str]]:
    """(scenario, strategy) → (fill rate, total cost) from a Markdown results table."""
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match:
            scenario, strategy, fill, total = match.groups()
            found[(scenario, strategy)] = (fill, total)
    return found


def run_cli() -> str:
    command = [
        sys.executable,
        "scripts/demo.py",
        "--reference",
        str(FIXTURE),
        "--horizon-days",
        "28",
    ]
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True).stdout


def test_demo_cli_runs_the_golden_path_reproducibly() -> None:
    first = run_cli()
    assert "Scenario comparison" in first and "What-if" in first
    for strategy in ("[reorder_point]", "[safety_stock]", "[dynamic]"):
        assert strategy in first
    assert "overrides={'lead_time_delta': 5}" in first
    assert "not evidence of real-world performance" in first

    def stable(text: str) -> list[str]:
        return [line for line in text.splitlines() if not line.startswith("run run_")]

    assert stable(run_cli()) == stable(first)


@pytest.mark.m5_local
@pytest.mark.skipif(not REFERENCE.is_dir(), reason="no M5 subset in data/reference/m5_subset")
def test_demo_and_guide_match_the_committed_validation_report() -> None:
    report = rows(ROOT / "docs" / "validation-report.md")
    assert len(report) == 6
    demo = load_demo()
    with demo.api_client(None, REFERENCE) as client:
        runs = demo.run_demo(client, "high_demand", demo.HORIZON_DAYS)
    for (scenario, strategy), (fill, total) in report.items():
        metrics = runs[scenario]["variant_metrics"][strategy]
        assert demo.fmt(metrics["fill_rate"], "pct") == fill, (scenario, strategy)
        assert demo.fmt(metrics["total_cost"], "usd") == total, (scenario, strategy)
    assert rows(ROOT / "docs" / "demo-guide.md") == report
