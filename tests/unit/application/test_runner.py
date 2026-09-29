"""Workflow runner, run store and pack discovery with a minimal dummy pack (no warehouse code)."""

from datetime import date, timedelta
from itertools import count
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from industrial_ai.application import (
    ComponentInfo,
    PackRunOutput,
    ResolvedRun,
    RunRequest,
    RunStatus,
    RunStore,
    ScenarioPack,
    WorkflowRunner,
    discover_packs,
    new_pack_registry,
)
from industrial_ai.application import pack as pack_module
from industrial_ai.core.errors import (
    DatasetAlreadyRegisteredError,
    RegistryError,
    RunFailedError,
    RunRequestError,
)
from industrial_ai.foundation.catalog import DatasetCatalog
from industrial_ai.foundation.datasets import SourceInfo, SourceType, build_dataset
from industrial_ai.foundation.provenance import Lineage
from industrial_ai.scenario import ScenarioRegistry, ScenarioSpec
from industrial_ai.simulation import RunContext, SimulationEngine, new_simulation_registry

from ..simulation.dummies import MeanForecast, StockSimulation, demand_dataset


class Params(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    demand_multiplier: float = Field(default=1.0, ge=0.1, le=5.0)


class Options(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    order_levels: tuple[int, ...] = (5, 50)
    fail: bool = False


class DummyPack:
    pack_id = "dummy"
    pack_version = "1.0.0"
    title = "Dummy"
    description = "Framework test pack."
    run_options_model: type[BaseModel] = Options
    requires_reference = False

    def components(self) -> list[ComponentInfo]:
        return [
            ComponentInfo(
                kind="simulation",
                component_id="stock_sim",
                version="1.0.0",
                description="Dummy",
                parameter_schema={},
            )
        ]

    def scenarios(self) -> ScenarioRegistry:
        registry = ScenarioRegistry("dummy", Params)
        registry.register(
            ScenarioSpec(scenario_id="base", version="1.0.0", pack="dummy", title="B")
        )
        registry.register(
            ScenarioSpec(
                scenario_id="high",
                version="1.0.0",
                pack="dummy",
                title="H",
                parameters={"demand_multiplier": 1.4},
            )
        )
        return registry

    def run(self, resolved: ResolvedRun) -> PackRunOutput:
        options = resolved.options
        assert isinstance(options, Options)
        if options.fail:
            raise RuntimeError("pipeline exploded")
        registry = new_simulation_registry()
        registry.register(MeanForecast())
        registry.register(StockSimulation())
        engine = SimulationEngine(registry)
        context = RunContext(
            run_id=resolved.run_id,
            seed=resolved.request.seed,
            start_date=date(2016, 1, 29),
            end_date=date(2016, 1, 28) + timedelta(days=resolved.request.horizon_days),
        )
        demand = demand_dataset()
        forecast = engine.run("mean_forecast", demand, None, {}, context)
        variants: dict[str, dict[str, JsonValue]] = {
            f"level_{level}": {"order_level": level} for level in options.order_levels
        }
        comparison = engine.compare(
            "stock_sim",
            demand,
            resolved.scenario,
            variants,
            context.with_upstream("forecast", forecast),
        )
        return PackRunOutput(
            comparison=comparison,
            supporting={"forecast": forecast},
            inputs={"demand": demand},
            labels=("prototype",),
        )


def make_runner(tmp_path: Path) -> WorkflowRunner:
    packs = new_pack_registry()
    packs.register(DummyPack())
    database = f"sqlite:///{tmp_path / 'runs.sqlite'}"
    ids = count(1)
    return WorkflowRunner(
        packs,
        RunStore(database, DatasetCatalog(database, tmp_path / "artifacts")),
        run_id_factory=lambda: f"run_{next(ids)}",
    )


def request(**changes: object) -> RunRequest:
    fields: dict[str, object] = {
        "pack": "dummy",
        "scenario_id": "base",
        "seed": 1,
        "horizon_days": 5,
    }
    fields.update(changes)
    return RunRequest.model_validate(fields)


def test_dummy_pack_satisfies_the_protocol() -> None:
    assert isinstance(DummyPack(), ScenarioPack)


def test_successful_run_is_recorded(tmp_path: Path) -> None:
    runner = make_runner(tmp_path)
    record = runner.run(request(scenario_id="high"))
    assert record.run_id == "run_1" and record.status is RunStatus.SUCCEEDED
    assert record.pack == "dummy" and record.pack_version == "1.0.0"
    assert record.scenario.parameters == {"demand_multiplier": 1.4}
    assert list(record.variant_metrics) == ["level_5", "level_50"]
    fill = {name: m["fill_rate"] for name, m in record.variant_metrics.items()}
    assert fill["level_50"] == 1.0 and (fill["level_5"] or 0) < 1.0
    assert record.supporting_metrics == {"forecast": {"items": 2.0}}
    assert set(record.outputs) == {"forecast.prediction", "level_5.ledger", "level_50.ledger"}
    assert record.inputs["demand"].content_hash == demand_dataset().metadata.content_hash
    assert runner.store.get("run_1") == record
    assert record.finished_at >= record.created_at


def test_overrides_merge_into_the_scenario(tmp_path: Path) -> None:
    runner = make_runner(tmp_path)
    record = runner.run(request(scenario_overrides={"demand_multiplier": 2.0}))
    assert record.scenario.parameters == {"demand_multiplier": 2.0}
    assert record.scenario_overrides == {"demand_multiplier": 2.0}


@pytest.mark.parametrize(
    "bad",
    [
        {"pack": "missing"},
        {"scenario_id": "missing"},
        {"scenario_version": "9.9.9"},
        {"scenario_overrides": {"demand_multiplier": 50}},
        {"scenario_overrides": {"unknown": 1}},
        {"options": {"order_levels": "many"}},
        {"options": {"surprise": True}},
    ],
)
def test_invalid_requests_raise_and_store_nothing(tmp_path: Path, bad: dict[str, object]) -> None:
    runner = make_runner(tmp_path)
    with pytest.raises(RunRequestError):
        runner.run(request(**bad))
    assert runner.store.list() == []


def test_failed_pipeline_is_stored_as_failed(tmp_path: Path) -> None:
    runner = make_runner(tmp_path)
    with pytest.raises(RunFailedError, match="exploded") as caught:
        runner.run(request(options={"fail": True}))
    assert isinstance(caught.value.__cause__, RuntimeError)
    (record,) = runner.store.list()
    assert caught.value.run_id == record.run_id
    assert record.status is RunStatus.FAILED
    assert record.error == "RuntimeError: pipeline exploded"
    assert record.variant_metrics == {} and record.outputs == {}


def test_runs_listed_newest_first_and_inputs_reused(tmp_path: Path) -> None:
    runner = make_runner(tmp_path)
    first, second = runner.run(request()), runner.run(request())
    assert [r.run_id for r in runner.store.list()] == [second.run_id, first.run_id]
    assert first.inputs == second.inputs  # identical input registered once, reused
    assert first.variant_metrics == second.variant_metrics


def test_same_dataset_id_with_different_content_is_refused(tmp_path: Path) -> None:
    runner = make_runner(tmp_path)
    runner.store.store_dataset(demand_dataset())
    changed = demand_dataset()
    data = changed.data.copy()
    data["quantity"] = data["quantity"] + (data.index == 0)
    tampered = build_dataset(
        dataset_id=changed.dataset_id,
        version=changed.version,
        schema=changed.schema,
        data=data,
        source=SourceInfo(name="tampered", source_type=SourceType.FIXTURE),
        lineage=Lineage(),
    )
    with pytest.raises(DatasetAlreadyRegisteredError):
        runner.store.store_dataset(tampered)


def test_discovery_rejects_entry_points_that_are_not_packs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeEntry:
        name = "broken"

        @staticmethod
        def load() -> object:
            return object()

    monkeypatch.setattr(pack_module, "entry_points", lambda group: [FakeEntry()])
    with pytest.raises(RegistryError, match="broken"):
        discover_packs()
