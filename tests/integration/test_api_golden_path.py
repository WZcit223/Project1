"""Gate 10: the full Golden Path through the Application API only (HTTP via TestClient).

Every step a client needs — discover packs, references, scenarios, strategies and models, create a
user scenario, run all scenarios, read results, time series, comparison, datasets and provenance —
goes through HTTP. No framework or pack function is called directly.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from industrial_ai.api.app import create_app
from industrial_ai.core.config import Environment, Settings

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "m5_like"
SCENARIOS = ["baseline", "high_demand", "demand_shock", "supply_disruption"]
STRATEGIES = ["reorder_point", "safety_stock", "dynamic"]


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    root = tmp_path_factory.mktemp("api")
    settings = Settings(
        env=Environment.TEST,
        data_dir=root,
        database_url=f"sqlite:///{root / 'api.sqlite'}",
        reference_dirs={"fixture": FIXTURE, "broken": root / "does_not_exist"},
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def run_body(scenario_id: str, **changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "pack": "warehouse",
        "reference_id": "fixture",
        "scenario_id": scenario_id,
        "seed": 20260927,
        "horizon_days": 84,
    }
    body.update(changes)
    return body


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def error_code(response: Any, status: int) -> str:
    assert response.status_code == status, response.text
    code: str = response.json()["error"]["code"]
    return code


@pytest.fixture(scope="module")
def runs(client: TestClient) -> dict[str, dict[str, Any]]:
    return {s: ok(client.post("/api/runs", json=run_body(s)), 201) for s in SCENARIOS}


def test_discovery_endpoints(client: TestClient) -> None:
    (pack,) = ok(client.get("/api/scenario-packs"))
    assert pack["pack_id"] == "warehouse" and pack["requires_reference"] is True
    assert set(SCENARIOS) <= set(pack["scenario_ids"])
    references = {r["reference_id"]: r["available"] for r in ok(client.get("/api/references"))}
    assert references == {"broken": False, "fixture": True}
    specs = ok(client.get("/api/scenarios", params={"pack": "warehouse"}))
    assert {s["scenario_id"] for s in specs} >= set(SCENARIOS)
    detail = ok(client.get("/api/scenarios/supply_disruption", params={"pack": "warehouse"}))
    assert detail["effective_parameters"]["supply_capacity_factor"] == 0.5
    assert "lead_time_delta" in detail["parameter_schema"]["properties"]
    strategies = ok(client.get("/api/strategies", params={"pack": "warehouse"}))
    assert sorted(s["component_id"] for s in strategies) == sorted(STRATEGIES)
    forecasts = ok(client.get("/api/models", params={"pack": "warehouse", "kind": "forecast"}))
    assert {m["component_id"] for m in forecasts} == {
        "seasonal_naive",
        "moving_average",
        "lightgbm",
    }
    generators = ok(client.get("/api/synthetic/generators"))
    assert {g["generator_id"] for g in generators} == {"rule_based", "statistical", "time_series"}


def test_golden_path_over_http(client: TestClient, runs: dict[str, dict[str, Any]]) -> None:
    for scenario_id, record in runs.items():
        assert record["status"] == "succeeded"
        assert record["scenario"]["scenario_id"] == scenario_id
        results = ok(client.get(f"/api/runs/{record['run_id']}/results"))
        assert list(results["variants"]) == STRATEGIES
        assert "fill_rate" in results["metric_ids"] and "total_cost" in results["metric_ids"]
        assert results["labels"] == ["prototype", "synthetic-data"]
    listed = {r["run_id"] for r in ok(client.get("/api/runs"))}
    assert {r["run_id"] for r in runs.values()} <= listed


def test_results_match_the_direct_golden_path(runs: dict[str, dict[str, Any]]) -> None:
    """HTTP adds no computation: same seed and fixture → same metrics as the runner-level test."""
    baseline = runs["baseline"]["variant_metrics"]
    assert baseline["reorder_point"]["fill_rate"] == pytest.approx(0.9063, abs=5e-4)


def test_timeseries_compare_and_datasets(
    client: TestClient, runs: dict[str, dict[str, Any]]
) -> None:
    run_id = runs["high_demand"]["run_id"]
    series = ok(
        client.get(
            f"/api/runs/{run_id}/timeseries",
            params={"variant": "dynamic", "table": "inventory_ledger", "column": "demand"},
        )
    )
    assert len(series["points"]) == 84
    ledger_link = runs["high_demand"]["outputs"]["dynamic.inventory_ledger"]
    preview = ok(
        client.get(f"/api/datasets/{ledger_link['dataset_id']}/preview", params={"limit": 3})
    )
    product = preview["rows"][0]["product_id"]
    one = ok(
        client.get(
            f"/api/runs/{run_id}/timeseries",
            params={
                "variant": "dynamic",
                "table": "inventory_ledger",
                "column": "demand",
                "filter": f"product_id:{product}",
            },
        )
    )
    assert sum(p["value"] for p in one["points"]) < sum(p["value"] for p in series["points"])

    rows = ok(
        client.get(
            "/api/runs/compare",
            params={"run_ids": ",".join(r["run_id"] for r in runs.values())},
        )
    )
    assert len(rows) == len(SCENARIOS) * len(STRATEGIES)
    assert {r["scenario_id"] for r in rows} == set(SCENARIOS)

    detail = ok(client.get(f"/api/datasets/{ledger_link['dataset_id']}"))
    assert detail["summary"]["content_hash"] == ledger_link["content_hash"]
    assert detail["provenance"]["scenario"]["scenario_id"] == "high_demand"
    demand_link = runs["high_demand"]["inputs"]["synthetic_demand"]
    input_hashes = {i["content_hash"] for i in detail["provenance"]["inputs"]}
    assert demand_link["content_hash"] in input_hashes
    datasets = ok(client.get("/api/datasets", params={"source_type": "synthetic"}))
    assert demand_link["dataset_id"] in {d["dataset_id"] for d in datasets}


def test_user_scenario_lifecycle(client: TestClient) -> None:
    spec = {
        "scenario_id": "promo_week",
        "version": "1.0.0",
        "pack": "warehouse",
        "title": "Promotion week",
        "parameters": {"shock_multiplier": 1.8, "shock_start_day": 7, "shock_duration_days": 7},
    }
    created = ok(client.post("/api/scenarios", json=spec), 201)
    assert created["source"] == "user"
    assert error_code(client.post("/api/scenarios", json=spec), 409) == "CONFLICT"
    bad = {**spec, "version": "1.0.1", "parameters": {"shock_multiplier": 99}}
    assert error_code(client.post("/api/scenarios", json=bad), 422) == "INVALID_SCENARIO"
    assert error_code(client.post("/api/scenarios", json={**spec, "pack": "x"}), 404) == "NOT_FOUND"
    record = ok(client.post("/api/runs", json=run_body("promo_week", horizon_days=28)), 201)
    assert record["scenario"]["source"] == "user"
    assert record["scenario"]["parameters"]["shock_multiplier"] == 1.8


def test_synthetic_generation_over_http(client: TestClient) -> None:
    request = {
        "generator_id": "rule_based",
        "dataset_id": "api_suppliers",
        "output_schema": {
            "schema_id": "api.supplier",
            "schema_version": "1.0.0",
            "fields": [
                {"name": "supplier_id", "dtype": "str"},
                {"name": "order_cost", "dtype": "float", "min": 0},
            ],
            "primary_key": ["supplier_id"],
        },
        "seed": 3,
        "size": {"rows": 4},
        "parameters": {
            "columns": {
                "supplier_id": {"kind": "sequence", "prefix": "SUP"},
                "order_cost": {"kind": "uniform", "low": 20, "high": 60, "decimals": 2},
            }
        },
    }
    summary = ok(client.post("/api/synthetic/generate", json=request), 201)
    assert summary["row_count"] == 4 and summary["source_type"] == "synthetic"
    detail = ok(client.get("/api/datasets/api_suppliers"))
    assert detail["provenance"]["component"]["id"] == "rule_based"
    assert detail["provenance"]["seed"] == 3


def test_errors_use_the_documented_shape(client: TestClient) -> None:
    response = client.post("/api/runs", json=run_body("baseline", reference_id="nope"))
    assert error_code(response, 422) == "INVALID_RUN_REQUEST"
    assert "unknown reference_id" in response.json()["error"]["message"]
    bad_option = run_body("baseline", options={"strategies": ["magic"]})
    assert error_code(client.post("/api/runs", json=bad_option), 422) == "INVALID_RUN_REQUEST"
    bad_body = {"pack": "warehouse"}
    assert error_code(client.post("/api/runs", json=bad_body), 422) == "VALIDATION_ERROR"
    assert error_code(client.get("/api/runs/run_missing"), 404) == "RUN_NOT_FOUND"
    assert error_code(client.get("/api/datasets/missing"), 404) == "DATASET_NOT_FOUND"
    missing_scenario = client.get("/api/scenarios/none", params={"pack": "warehouse"})
    assert error_code(missing_scenario, 404) == "NOT_FOUND"
    failed = client.post("/api/runs", json=run_body("baseline", reference_id="broken"))
    assert error_code(failed, 500) == "RUN_FAILED"
    run_id = failed.json()["error"]["details"]["run_id"]
    assert ok(client.get(f"/api/runs/{run_id}"))["status"] == "failed"
