"""Scripted demo: the Golden Path through the Application API only (docs/demo-guide.md).

    uv run python scripts/demo.py                    # in-process API, committed M5 reference subset
    uv run python scripts/demo.py --api http://127.0.0.1:8000   # against a running server

Runs baseline and one stress scenario for the three strategies, then a what-if (one parameter
changed, same reference, scenario version and seed), and prints the comparison. Every number comes
from the API; with the same commit, reference subset and seed the output is identical.
"""

import argparse
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx2

SEED = 20260927
HORIZON_DAYS = 91
KPIS = (
    ("fill_rate", "Fill rate", "pct"),
    ("stockout_day_rate", "Stockout-day rate", "pct"),
    ("ordering_cost", "Ordering cost", "usd"),
    ("holding_cost", "Holding cost", "usd"),
    ("lost_sales_cost", "Lost-sales cost", "usd"),
    ("total_cost", "Total cost", "usd"),
)
STRATEGIES = ("reorder_point", "safety_stock", "dynamic")


@contextmanager
def api_client(url: str | None, reference: Path) -> Iterator[httpx2.Client]:
    """HTTP client for a running API, or for an in-process API on a temporary database."""
    if url:
        with httpx2.Client(base_url=url, timeout=600) as client:
            yield client
        return
    from fastapi.testclient import TestClient

    from industrial_ai.api.app import create_app
    from industrial_ai.core.config import Environment, Settings

    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(
            env=Environment.DEMO,
            data_dir=Path(tmp),
            database_url=f"sqlite:///{Path(tmp) / 'demo.sqlite'}",
            reference_dirs={"m5_subset": reference},
        )
        with TestClient(create_app(settings)) as client:
            yield client


def post_run(client: httpx2.Client, **body: Any) -> dict[str, Any]:
    response = client.post("/api/runs", json=body)
    if response.status_code != 201:
        raise SystemExit(f"run failed: {response.status_code} {response.text}")
    record: dict[str, Any] = response.json()
    return record


def run_demo(client: httpx2.Client, scenario: str, horizon_days: int) -> dict[str, dict[str, Any]]:
    """Baseline, one stress scenario and a what-if (lead_time_delta +5) on identical settings."""
    base: dict[str, Any] = {
        "pack": "warehouse",
        "reference_id": "m5_subset",
        "seed": SEED,
        "horizon_days": horizon_days,
    }
    baseline = post_run(client, scenario_id="baseline", **base)
    stress = post_run(client, scenario_id=scenario, **base)
    what_if = post_run(
        client,
        scenario_id="baseline",
        scenario_version=baseline["scenario"]["version"],
        scenario_overrides={"lead_time_delta": 5},
        **base,
    )
    return {"baseline": baseline, scenario: stress, "what-if": what_if}


def fmt(value: float | None, kind: str) -> str:
    if value is None:
        return "–"
    return f"{value:.1%}" if kind == "pct" else f"${value:,.0f}"


def table(title: str, runs: dict[str, dict[str, Any]]) -> str:
    lines = [f"\n{title}", "-" * len(title)]
    header = f"{'KPI':<20}" + "".join(f"{name:>22}" for name in runs)
    for strategy in STRATEGIES:
        lines += [f"\n[{strategy}]", header]
        for metric_id, label, kind in KPIS:
            row = f"{label:<20}"
            for record in runs.values():
                row += f"{fmt(record['variant_metrics'][strategy][metric_id], kind):>22}"
            lines.append(row)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the scripted Golden Path demo.")
    parser.add_argument("--api", help="base URL of a running API (default: in-process)")
    parser.add_argument("--reference", type=Path, default=Path("data/reference/m5_subset"))
    parser.add_argument("--scenario", default="high_demand")
    parser.add_argument("--horizon-days", type=int, default=HORIZON_DAYS)
    args = parser.parse_args()

    with api_client(args.api, args.reference.resolve()) as client:
        print("Scenario packs:", [p["pack_id"] for p in client.get("/api/scenario-packs").json()])
        runs = run_demo(client, args.scenario, args.horizon_days)
        baseline, stress, what_if = runs["baseline"], runs[args.scenario], runs["what-if"]
        for record in (baseline, stress, what_if):
            scenario = record["scenario"]
            print(
                f"run {record['run_id']}: {scenario['scenario_id']} {scenario['version']} "
                f"overrides={record['scenario_overrides']}"
            )
        comparison = {"baseline": baseline, args.scenario: stress}
        print(table("Scenario comparison (same seed, same demand stream)", comparison))
        what_if_view = {"baseline": baseline, "what-if": what_if}
        print(table("What-if: baseline with lead_time_delta = +5 days", what_if_view))
        wape = baseline["supporting_metrics"]["forecast"]["wape"]
        print(f"\nForecast WAPE (baseline, seasonal naive): {wape:.3f}")
        print(
            "\nPrototype · synthetic operational data · not evidence of real-world performance "
            "(see docs/validation-report.md)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
