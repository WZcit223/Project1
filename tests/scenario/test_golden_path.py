"""Golden Path (Gate 9): the most important integration test (CLAUDE.md §11).

M5-shaped fixture → canonical retail bundle → synthetic operations and scenario demand → forecast →
inventory simulation × 3 strategies → 4 scenarios → metrics, executed by the framework's workflow
runner through the warehouse pack discovered via its entry point, persisted and reproducible.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from industrial_ai.application import (
    RunRecord,
    RunRequest,
    RunStatus,
    RunStore,
    WorkflowRunner,
    discover_packs,
)
from industrial_ai.core.errors import RunFailedError, RunNotFoundError, RunRequestError
from industrial_ai.foundation.catalog import DatasetCatalog
from industrial_ai_warehouse.scenarios import BUILTIN_SCENARIO_IDS

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "m5_like"
STRATEGIES = ["reorder_point", "safety_stock", "dynamic"]
SEED = 20260927


def request(scenario: str, **changes: object) -> RunRequest:
    fields: dict[str, object] = {
        "pack": "warehouse",
        "scenario_id": scenario,
        "seed": SEED,
        "horizon_days": 84,
        "reference": str(FIXTURE),
    }
    fields.update(changes)
    return RunRequest.model_validate(fields)


@pytest.fixture(scope="module")
def runner(tmp_path_factory: pytest.TempPathFactory) -> Iterator[WorkflowRunner]:
    root = tmp_path_factory.mktemp("golden")
    database = f"sqlite:///{root / 'runs.sqlite'}"
    store = RunStore(database, DatasetCatalog(database, root / "artifacts"))
    yield WorkflowRunner(discover_packs(), store)


@pytest.fixture(scope="module")
def runs(runner: WorkflowRunner) -> dict[str, RunRecord]:
    return {scenario_id: runner.run(request(scenario_id)) for scenario_id in BUILTIN_SCENARIO_IDS}


def test_pack_is_discovered_through_its_entry_point(runner: WorkflowRunner) -> None:
    assert ("warehouse", "0.1.0") in runner.packs


@pytest.mark.parametrize("scenario_id", BUILTIN_SCENARIO_IDS)
def test_every_scenario_runs_end_to_end(runs: dict[str, RunRecord], scenario_id: str) -> None:
    record = runs[scenario_id]
    assert record.status is RunStatus.SUCCEEDED and record.error is None
    assert record.scenario.scenario_id == scenario_id
    assert list(record.variant_metrics) == STRATEGIES
    for metrics in record.variant_metrics.values():
        assert metrics["fill_rate"] is not None
        assert metrics["total_cost"] == pytest.approx(
            (metrics["ordering_cost"] or 0)
            + (metrics["holding_cost"] or 0)
            + (metrics["lost_sales_cost"] or 0)
        )
    assert record.supporting_metrics["forecast"]["wape"] is not None
    assert record.labels == ("prototype", "synthetic-data")


def test_runs_are_persisted_with_their_datasets(
    runner: WorkflowRunner, runs: dict[str, RunRecord]
) -> None:
    record = runs["baseline"]
    assert runner.store.get(record.run_id) == record
    assert {r.run_id for r in runner.store.list()} >= {r.run_id for r in runs.values()}
    catalog = runner.store.catalog
    expected_outputs = {"forecast.prediction"} | {
        f"{s}.{t}" for s in STRATEGIES for t in ("inventory_ledger", "purchase_order")
    }
    assert set(record.outputs) == expected_outputs
    for link in (*record.inputs.values(), *record.outputs.values()):
        dataset = catalog.get(link.dataset_id, link.version)  # hash re-verified on load
        assert dataset.metadata.content_hash == link.content_hash


def test_provenance_links_results_to_scenario_demand(
    runner: WorkflowRunner, runs: dict[str, RunRecord]
) -> None:
    record = runs["high_demand"]
    catalog = runner.store.catalog
    ledger = record.outputs["dynamic.inventory_ledger"]
    provenance = catalog.get(ledger.dataset_id, ledger.version).provenance
    input_hashes = {i.content_hash for i in provenance.inputs}
    assert record.inputs["synthetic_demand"].content_hash in input_hashes
    assert provenance.scenario is not None
    assert provenance.scenario.scenario_id == "high_demand"
    assert provenance.seed == SEED
    demand = record.inputs["synthetic_demand"]
    demand_provenance = catalog.get(demand.dataset_id, demand.version).provenance
    assert demand_provenance.component is not None
    assert demand_provenance.component.id == "time_series"


def test_golden_path_is_reproducible(runner: WorkflowRunner, runs: dict[str, RunRecord]) -> None:
    again = runner.run(request("baseline"))
    first = runs["baseline"]
    assert again.run_id != first.run_id
    assert again.variant_metrics == first.variant_metrics
    assert again.supporting_metrics == first.supporting_metrics
    for name, link in first.outputs.items():
        assert again.outputs[name].content_hash == link.content_hash


def test_scenario_overrides_are_applied_and_recorded(
    runner: WorkflowRunner, runs: dict[str, RunRecord]
) -> None:
    record = runner.run(request("baseline", scenario_overrides={"lead_time_delta": 10}))
    assert record.scenario_overrides == {"lead_time_delta": 10}
    assert record.scenario.parameters == {"lead_time_delta": 10}
    base = runs["baseline"].variant_metrics["reorder_point"]["fill_rate"]
    changed = record.variant_metrics["reorder_point"]["fill_rate"]
    assert base is not None and changed is not None and changed < base


@pytest.mark.parametrize(
    "bad",
    [
        {"pack": "maintenance"},
        {"scenario_id": "unknown"},
        {"scenario_overrides": {"demand_multiplier": 99}},
        {"scenario_overrides": {"demand_multiplyer": 1.2}},
        {"options": {"strategies": ["magic"]}},
        {"options": {"forecast_model": "prophet"}},
        {"options": {"reference_dir": "/tmp"}},
        {"reference": None},
    ],
)
def test_invalid_requests_are_rejected_before_running(
    runner: WorkflowRunner, bad: dict[str, object]
) -> None:
    before = len(runner.store.list())
    with pytest.raises(RunRequestError):
        runner.run(request("baseline", **bad))
    assert len(runner.store.list()) == before


def test_failing_pipeline_is_recorded_as_failed_and_raises(
    runner: WorkflowRunner, tmp_path: Path
) -> None:
    with pytest.raises(RunFailedError) as caught:
        runner.run(request("baseline", reference=str(tmp_path / "missing")))
    failed = runner.store.list()[0]
    assert failed.run_id == caught.value.run_id
    assert failed.status is RunStatus.FAILED
    assert failed.error and not failed.variant_metrics and not failed.outputs
    with pytest.raises(RunNotFoundError):
        runner.store.get("run_does_not_exist")
