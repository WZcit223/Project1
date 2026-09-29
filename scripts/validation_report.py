"""Generate ``docs/validation-report.md`` (TASK-VAL-001, docs/validation.md §6).

    uv run python scripts/validation_report.py

The report keeps four validation categories apart (docs/validation.md §1):

- V1 Software / framework correctness — unit, contract, architecture and data-structure tests.
- V2 Framework integration / Golden Path — workflow runner, HTTP API and browser UI end to end.
- V3 Scenario & reference-data validation — scenario behaviour checks, plus checks and descriptive
  comparisons on the committed M5 reference subset (store-level retail sales used as the reference
  demand environment; all operational data is synthetic).
- V4 Real operational validation — not performed (future; needs real warehouse operations data).

Test results come from pytest (JUnit XML); descriptive numbers are computed with the application's
own code paths. Nothing is entered by hand. Exit code 1 if any test fails.
"""

import argparse
import json
import platform
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import JsonValue

from industrial_ai.application import RunRequest, RunStore, WorkflowRunner, discover_packs
from industrial_ai.foundation.catalog import DatasetCatalog
from industrial_ai.foundation.validation import ValidationReport, validate_bundle
from industrial_ai.simulation import RunContext, SimulationEngine
from industrial_ai_warehouse.adapters.m5 import M5Adapter
from industrial_ai_warehouse.generators import (
    DemandConfig,
    build_hybrid_bundle,
    generate_operations,
    generate_synthetic_demand,
)
from industrial_ai_warehouse.pack import simulation_registry
from industrial_ai_warehouse.scenarios import BUILTIN_SCENARIO_IDS

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data" / "reference" / "m5_subset"
OUTPUT = ROOT / "docs" / "validation-report.md"
SEED = 20260927
HORIZON_DAYS = 91
STRATEGIES = ("reorder_point", "safety_stock", "dynamic")
FORECAST_MODELS = ("seasonal_naive", "moving_average", "lightgbm")
GOLDEN_PATH_FORECAST = "seasonal_naive"
"""Explicit, and identical to scripts/demo.py and the UI default (docs/demo-guide.md)."""
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

V3_MARKERS = "m5_local or scenario_checks"
"""V3 = every test marked m5_local (committed M5 subset) or scenario_checks (scenario behaviour)."""
NOT_V3 = f"not ({V3_MARKERS})"

SUITES: dict[str, tuple[str, str, list[str]]] = {
    "V1": (
        "Software / framework correctness",
        "Unit and contract tests of every layer; architecture import rules (the framework never "
        "imports packs, layer dependencies, the UI imports no framework module); synthetic-data "
        "structure (schema, constraints, relationships, reproducibility, provenance); metric "
        "definitions; failure modes.",
        ["tests/unit", "-m", NOT_V3],
    ),
    "V2": (
        "Framework integration / Golden Path",
        "End to end on the M5-shaped test fixture: canonical data → synthetic data → forecast → "
        "inventory × strategies × scenarios → metrics, through the workflow runner, the HTTP "
        "Application API and the browser UI; persisted datasets with verified hashes; provenance; "
        "reproducibility; no look-ahead; error handling.",
        [
            "tests/integration",
            "tests/scenario/test_golden_path.py",
            "tests/ui",
            "-m",
            NOT_V3,
        ],
    ),
    "V3": (
        "Scenario & reference-data validation",
        "Scenario behaviour checks (docs/validation.md §4) on the fixture, and tests on the "
        "committed "
        "M5 reference subset; descriptive reference-data results follow in §3.2.",
        ["tests", "-m", V3_MARKERS],
    ),
}


# --- test suites ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class SuiteResult:
    key: str
    title: str
    scope: str
    command: str
    tests: int
    failures: int
    errors: int
    skipped: int
    seconds: float
    per_module: dict[str, int]
    failed: list[str]

    @property
    def passed(self) -> int:
        return self.tests - self.failures - self.errors - self.skipped

    @property
    def ok(self) -> bool:
        return self.tests > 0 and self.failures == 0 and self.errors == 0


def run_suite(key: str, workdir: Path) -> SuiteResult:
    """Run one pytest selection and summarise pytest's own JUnit XML counts."""
    title, scope, selection = SUITES[key]
    xml_path = workdir / f"{key}.xml"
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *selection]
    subprocess.run([*command, f"--junitxml={xml_path}"], cwd=ROOT, check=False, capture_output=True)
    return summarise_junit(key, title, scope, "uv run pytest " + " ".join(
        f'"{a}"' if " " in a else a for a in selection
    ), xml_path)  # fmt: skip


def partitioned(suites: list[SuiteResult], collected: int) -> bool:
    return sum(s.tests for s in suites) == collected


def collected_tests() -> int:
    """Number of tests pytest collects for the whole suite (to prove V1-V3 partition it)."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    last = [line for line in result.stdout.splitlines() if "collected" in line][-1]
    return int(last.split()[0])


def summarise_junit(key: str, title: str, scope: str, command: str, path: Path) -> SuiteResult:
    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root[0]
    per_module: dict[str, int] = {}
    failed = []
    for case in suite.iter("testcase"):
        module = case.get("classname", "").replace(".", "/") + ".py"
        per_module[module] = per_module.get(module, 0) + 1
        if case.find("failure") is not None or case.find("error") is not None:
            failed.append(f"{module}::{case.get('name')}")
    return SuiteResult(
        key=key,
        title=title,
        scope=scope,
        command=command,
        tests=int(suite.get("tests", 0)),
        failures=int(suite.get("failures", 0)),
        errors=int(suite.get("errors", 0)),
        skipped=int(suite.get("skipped", 0)),
        seconds=float(suite.get("time", 0.0)),
        per_module=dict(sorted(per_module.items())),
        failed=failed,
    )


# --- reference data (descriptive) ----------------------------------------------------------------


@dataclass(frozen=True)
class DemandStats:
    series: int
    days: int
    mean_per_series_day: float
    mean_per_selling_day: float
    """Mean over series-days with sales > 0."""
    cv_daily_total: float
    zero_share: float
    weekday_index: tuple[float, ...]


@dataclass(frozen=True)
class CheckCounts:
    passed: int
    failed: int
    skipped: int


@dataclass(frozen=True)
class ReferenceResult:
    source: dict[str, str]
    series: int
    first_date: date
    last_date: date
    adapter: CheckCounts
    hybrid: CheckCounts
    reference_stats: DemandStats
    synthetic_stats: DemandStats
    item_mean_correlation: float
    forecast_window: tuple[date, date]
    forecasts: dict[str, dict[str, float | None]]


def demand_stats(frame: pd.DataFrame) -> DemandStats:
    daily = frame.groupby("date")["quantity"].sum()
    by_weekday = daily.groupby(pd.to_datetime(daily.index).dayofweek).mean().reindex(range(7))
    return DemandStats(
        series=int(frame.groupby(["product_id", "store_id"]).ngroups),
        days=int(frame["date"].nunique()),
        mean_per_series_day=float(frame["quantity"].mean()),
        mean_per_selling_day=float(frame.loc[frame["quantity"] > 0, "quantity"].mean()),
        cv_daily_total=float(daily.std() / daily.mean()),
        zero_share=float((frame["quantity"] == 0).mean()),
        weekday_index=tuple(round(float(v / daily.mean()), 3) for v in by_weekday),
    )


def counts(report: ValidationReport) -> CheckCounts:
    status = [r.status.value for r in report.results]
    return CheckCounts(status.count("passed"), status.count("failed"), status.count("skipped"))


def reference_checks() -> ReferenceResult:
    """Checks and descriptive comparisons on the committed M5 reference subset."""
    source = json.loads((REFERENCE / "SOURCE.json").read_text(encoding="utf-8"))
    retail = M5Adapter().load(REFERENCE)
    hybrid = build_hybrid_bundle(retail, generate_operations(retail, SEED))
    sales = retail.table("sales").data.copy()
    sales["date"] = pd.to_datetime(sales["date"])
    last = sales["date"].max().date()

    # Last 365 observed days of reference sales vs. synthetic baseline demand for the horizon.
    recent = sales[sales["date"] > pd.Timestamp(last - timedelta(days=365))]
    synthetic = generate_synthetic_demand(
        retail, DemandConfig(start=last + timedelta(days=1), periods=HORIZON_DAYS), SEED
    ).data.copy()
    synthetic["date"] = pd.to_datetime(synthetic["date"])
    reference_means = recent.groupby("product_id")["quantity"].mean()
    synthetic_means = synthetic.groupby("product_id")["quantity"].mean()
    correlation = float(
        np.corrcoef(reference_means, synthetic_means.reindex(reference_means.index))[0, 1]
    )

    # Forecast backtest on reference sales: weekly origins over the last 26 weeks of data.
    engine = SimulationEngine(simulation_registry())
    window = (last - timedelta(days=181), last)
    context = RunContext(
        run_id="validation.forecast", seed=SEED, start_date=window[0], end_date=window[1]
    )
    params: dict[str, JsonValue] = {
        "entity_columns": ["product_id", "store_id"],
        "input_table": "sales",
    }
    forecasts = {}
    for model in FORECAST_MODELS:
        result = engine.run(model, retail, None, params, context)
        forecasts[model] = {m: result.metric(m).value for m in ("wape", "mae", "bias")}

    return ReferenceResult(
        source={
            k: str(source[k])
            for k in ("dataset_name", "source_url", "download_date", "license_notes")
        },
        series=int(sales.groupby(["product_id", "store_id"]).ngroups),
        first_date=sales["date"].min().date(),
        last_date=last,
        adapter=counts(validate_bundle(retail)),
        hybrid=counts(validate_bundle(hybrid)),
        reference_stats=demand_stats(recent),
        synthetic_stats=demand_stats(synthetic),
        item_mean_correlation=correlation,
        forecast_window=window,
        forecasts=forecasts,
    )


@dataclass(frozen=True)
class GoldenPathResult:
    metrics: dict[str, dict[str, dict[str, float | None]]]
    """scenario → strategy → metric."""
    reproducible: bool


def golden_path_on_reference(workdir: Path) -> GoldenPathResult:
    """Golden Path via the workflow runner on the reference subset: 4 scenarios × 3 strategies."""
    database = f"sqlite:///{workdir / 'runs.sqlite'}"
    store = RunStore(database, DatasetCatalog(database, workdir / "artifacts"))
    runner = WorkflowRunner(discover_packs(), store)

    def run(scenario_id: str) -> dict[str, dict[str, float | None]]:
        request = RunRequest(
            pack="warehouse",
            scenario_id=scenario_id,
            seed=SEED,
            horizon_days=HORIZON_DAYS,
            reference_id="m5_subset",
            reference=str(REFERENCE),
            options={"forecast_model": GOLDEN_PATH_FORECAST},
        )
        return runner.run(request).variant_metrics

    metrics = {s: run(s) for s in BUILTIN_SCENARIO_IDS}
    return GoldenPathResult(metrics=metrics, reproducible=run("baseline") == metrics["baseline"])


# --- rendering ------------------------------------------------------------------------------------


def fmt(value: float | None, kind: str = "num") -> str:
    if value is None:
        return "–"
    if kind == "pct":
        return f"{value:.1%}"
    if kind == "usd":
        return f"${value:,.0f}"
    return f"{value:,.3f}"


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def render(
    suites: list[SuiteResult], collected: int, ref: ReferenceResult, gp: GoldenPathResult
) -> str:
    categorised = sum(s.tests for s in suites)
    coverage_note = (
        "every test is reported under exactly one category."
        if partitioned(suites, collected)
        else "**MISMATCH: some tests are in no category or in several.**"
    )
    commit = git("rev-parse", "--short", "HEAD")
    dirty = " (plus uncommitted changes)" if git("status", "--porcelain", "-uno") else ""
    lines = [
        "# Validation Report — v0.1",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by `scripts/validation_report.py` from "
        f"commit `{commit}`{dirty} on branch `{git('branch', '--show-current')}`. Python "
        f"{platform.python_version()}, pandas {version('pandas')}, numpy {version('numpy')}, "
        f"lightgbm {version('lightgbm')}; seed {SEED}. Categories as defined in "
        "[validation.md §1](validation.md#1-validation-categories).",
        "",
        "> **Claim.** *The framework validates synthetic data generation and scenario execution at",
        "> the prototype level.* No claim is made that synthetic data, forecasts or strategy",
        "> results represent a real warehouse: real operational validation (V4) was **not**",
        "> performed.",
        "",
        "## Summary",
        "",
        "| Category | Evidence | Result |",
        "|---|---|---|",
    ]
    for s in suites:
        lines.append(
            f"| **{s.key}** {s.title} | {s.tests} tests: {s.passed} passed, "
            f"{s.failures + s.errors} failed, {s.skipped} skipped | "
            f"{'✅ pass' if s.ok else '❌ FAIL'} |"
        )
    lines += [
        "| **V3** reference data (descriptive) | M5 subset: data checks "
        f"{ref.adapter.passed + ref.hybrid.passed} passed / "
        f"{ref.adapter.failed + ref.hybrid.failed} failed; calibration comparison, forecast "
        "backtest, Golden Path smoke run (§3.2) | "
        f"{'✅ checks pass' if not ref.adapter.failed + ref.hybrid.failed else '❌ FAIL'}; "
        "comparisons descriptive |",
        "| **V4** Real operational validation | — | ⛔ not performed (future) |",
        "",
        f"Coverage: V1 + V2 + V3 = {categorised} of {collected} tests collected by pytest — "
        + coverage_note,
        "",
    ]
    for number, s in enumerate(suites, start=1):
        heading = f"## {number}. {s.key} — {s.title}"
        if s.key == "V3":
            heading += "\n\n### 3.1 Tests"
        lines += [heading, "", s.scope, "", f"`{s.command}` — {s.seconds:.0f} s", ""]
        lines += ["| Test module | Tests |", "|---|---|"]
        lines += [f"| `{module}` | {n} |" for module, n in s.per_module.items()]
        if s.failed:
            lines += ["", "**Failed:**", *[f"- `{f}`" for f in s.failed]]
        lines.append("")
    lines += render_reference(ref, gp)
    lines += [
        "## 4. V4 — Real operational validation: not performed",
        "",
        "Not validated in v0.1 and not claimed:",
        "",
        "- that the synthetic operational data (warehouses, suppliers, lead times, costs, initial "
        "inventory, purchase orders) resembles any real company's operations;",
        "- that synthetic demand reproduces real demand beyond the descriptive statistics in §3.2 "
        "(known gap: runs of zero-sales days in the reference data are not reproduced);",
        "- that any replenishment strategy is economically or operationally better in reality — "
        "strategy results compare strategies under identical simulated conditions only;",
        "- that M5 sales equal demand: M5 records observed sales and has no inventory data; zero "
        "observed sales may reflect true zero demand, stockouts or other demand censoring, which "
        "the reference cannot distinguish. M5 serves as a reference demand/sales environment, not "
        "as true demand and not as warehouse operational data.",
        "",
        "Needed for V4: real SKU-level demand with stockout flags, inventory snapshots, "
        "purchase-order history with actual lead times, cost data, and a backtest or pilot against "
        "current practice ([future-roadmap.md §2.1](future-roadmap.md)).",
        "",
    ]
    return "\n".join(lines)


def render_reference(ref: ReferenceResult, gp: GoldenPathResult) -> list[str]:
    r, s = ref.reference_stats, ref.synthetic_stats
    level_gap = s.mean_per_series_day / r.mean_per_series_day - 1
    lines = [
        "### 3.2 Reference data: the committed M5 subset",
        "",
        "**What M5 is here.** Store-level retail **sales** (Walmart store CA_1, department "
        "FOODS_3, "
        "top 50 items) with calendar and prices. It is the **reference demand/sales environment**: "
        "synthetic demand is calibrated on it and forecasts are backtested on it. It is **not** "
        "warehouse operational data — warehouses, suppliers, lead times, costs, initial inventory "
        "and purchase orders are all **synthetic** (the Hybrid Validation Environment).",
        "",
        f"Source: {ref.source['dataset_name']} ({ref.source['source_url']}), downloaded "
        f"{ref.source['download_date']}. {ref.source['license_notes']} {ref.series} series, "
        f"{ref.first_date} … {ref.last_date}.",
        "",
        "| Data check | Passed | Failed | Skipped |",
        "|---|---|---|---|",
        f"| Canonical retail bundle from the M5 adapter (schema, constraints, keys) | "
        f"{ref.adapter.passed} | {ref.adapter.failed} | {ref.adapter.skipped} |",
        f"| Hybrid environment: reference + synthetic operations (seed {SEED}) | "
        f"{ref.hybrid.passed} | {ref.hybrid.failed} | {ref.hybrid.skipped} |",
        "",
        f"**Calibration comparison** (descriptive, no pass/fail): last {r.days} days of reference "
        f"sales vs. {s.days} days of synthetic baseline demand (time_series generator, "
        f"seed {SEED}).",
        "",
        "| Statistic | Reference sales | Synthetic demand |",
        "|---|---|---|",
        f"| Series | {r.series} | {s.series} |",
        f"| Mean units per series-day | {fmt(r.mean_per_series_day)} | "
        f"{fmt(s.mean_per_series_day)} |",
        f"| Mean units per series-day with sales > 0 | {fmt(r.mean_per_selling_day)} | "
        f"{fmt(s.mean_per_selling_day)} |",
        f"| Coefficient of variation of daily totals | {fmt(r.cv_daily_total)} | "
        f"{fmt(s.cv_daily_total)} |",
        f"| Share of zero series-days | {fmt(r.zero_share, 'pct')} | {fmt(s.zero_share, 'pct')} |",
        "| Weekday index (daily mean ÷ overall mean) | "
        + ", ".join(f"{d} {v}" for d, v in zip(WEEKDAYS, r.weekday_index, strict=True))
        + " | "
        + ", ".join(f"{d} {v}" for d, v in zip(WEEKDAYS, s.weekday_index, strict=True))
        + " |",
        f"| Correlation of per-item mean units | — | {fmt(ref.item_mean_correlation)} |",
        "",
        f"Reading: synthetic mean demand is {level_gap:+.0%} versus the reference mean. The "
        f"reference has {fmt(r.zero_share, 'pct')} zero-sales series-days, the synthetic data "
        f"{fmt(s.zero_share, 'pct')}; on days with sales the means are close "
        f"({fmt(r.mean_per_selling_day)} vs. {fmt(s.mean_per_selling_day)}), so the gap comes "
        "mostly from zero observed sales that the generator does not reproduce. Zero observed "
        "sales in the M5 reference may reflect true zero demand, stockouts or other forms of "
        "demand censoring; the reference dataset does not provide sufficient inventory "
        "information to distinguish these causes directly (zero observed sales ≠ confirmed "
        "stockout). Per-item levels are strongly correlated and the weekday pattern is "
        "reproduced. The synthetic horizon (after the reference data) and the reference year "
        "cover different seasons. Zero-run modelling is on the roadmap (P1).",
        "",
        f"**Forecast backtest on reference sales** (weekly origins {ref.forecast_window[0]} … "
        f"{ref.forecast_window[1]}, 28-day horizon, history strictly before each origin):",
        "",
        "| Model | WAPE | MAE (units) | Bias |",
        "|---|---|---|---|",
    ]
    for model, m in ref.forecasts.items():
        lines.append(
            f"| `{model}` | {fmt(m['wape'])} | {fmt(m['mae'])} | {fmt(m['bias'], 'pct')} |"
        )
    lines += [
        "",
        f"**Golden Path smoke run on the reference subset** (workflow runner; {HORIZON_DAYS}-day "
        f"synthetic horizon; seasonal-naive forecast; seed {SEED}). A repeated baseline run "
        f"reproduced identical metrics: **{'yes' if gp.reproducible else 'NO'}**. "
        "Descriptive only — "
        "not evidence that any strategy is better in reality.",
        "",
        "| Scenario | Strategy | Fill rate | Stockout-day rate | Ordering cost | Holding cost | "
        "Lost-sales cost | Total cost |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for scenario, variants in gp.metrics.items():
        for strategy in STRATEGIES:
            m = variants[strategy]
            lines.append(
                f"| {scenario} | {strategy} | {fmt(m['fill_rate'], 'pct')} | "
                f"{fmt(m['stockout_day_rate'], 'pct')} | {fmt(m['ordering_cost'], 'usd')} | "
                f"{fmt(m['holding_cost'], 'usd')} | {fmt(m['lost_sales_cost'], 'usd')} | "
                f"{fmt(m['total_cost'], 'usd')} |"
            )
    lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate docs/validation-report.md.")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        suites = [run_suite(key, workdir) for key in SUITES]
        collected = collected_tests()
        reference = reference_checks()
        golden = golden_path_on_reference(workdir)
    args.output.write_text(render(suites, collected, reference, golden), encoding="utf-8")
    print(f"wrote {args.output}")
    for s in suites:
        print(f"{s.key}: {s.tests} tests, {s.failures + s.errors} failed, {s.skipped} skipped")
    print(f"collected: {collected}; categorised: {sum(s.tests for s in suites)}")
    ok = all(s.ok for s in suites) and golden.reproducible and partitioned(suites, collected)
    return 0 if ok and not (reference.adapter.failed or reference.hybrid.failed) else 1


if __name__ == "__main__":
    sys.exit(main())
