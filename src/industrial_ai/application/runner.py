"""Workflow runner: validate a run request, execute the pack's pipeline, persist the run.

The runner is domain-neutral orchestration (docs/application-api.md §5): it resolves the pack and
scenario, validates overrides and options, calls ``pack.run`` and stores what the run produced.
A failing pipeline is recorded as a ``failed`` run and the error is re-raised — never reported as
success.
"""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import ValidationError

from industrial_ai.application.models import (
    DatasetLink,
    ResolvedRun,
    RunRecord,
    RunRequest,
    RunStatus,
)
from industrial_ai.application.pack import PackRegistry, PackRunOutput, ScenarioPack
from industrial_ai.application.store import RunStore
from industrial_ai.core.errors import PluginNotFoundError, RunRequestError, ScenarioValidationError
from industrial_ai.simulation import SimulationResult

logger = logging.getLogger(__name__)


def new_run_id() -> str:
    now = datetime.now(UTC)
    return f"run_{now:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"


class WorkflowRunner:
    def __init__(
        self,
        packs: PackRegistry,
        store: RunStore,
        run_id_factory: Callable[[], str] = new_run_id,
    ) -> None:
        self._packs = packs
        self._store = store
        self._new_run_id = run_id_factory

    @property
    def packs(self) -> PackRegistry:
        return self._packs

    @property
    def store(self) -> RunStore:
        return self._store

    def resolve(self, request: RunRequest) -> tuple[ScenarioPack, ResolvedRun]:
        """Validate ``request`` against the pack: scenario, overrides, options.

        Raises:
            RunRequestError: unknown pack or scenario, invalid overrides or options.
        """
        try:
            pack = self._packs.get(request.pack)
            spec = pack.scenarios().get(request.scenario_id, request.scenario_version)
        except PluginNotFoundError as exc:
            raise RunRequestError(str(exc)) from exc
        effective = spec.model_copy(
            update={"parameters": {**spec.parameters, **request.scenario_overrides}}
        )
        try:
            pack.scenarios().validate_parameters(effective)
            options = pack.run_options_model.model_validate(request.options)
        except (ScenarioValidationError, ValidationError) as exc:
            raise RunRequestError(f"invalid run request: {exc}") from exc
        resolved = ResolvedRun(
            run_id=self._new_run_id(), request=request, scenario=effective, options=options
        )
        return pack, resolved

    def run(self, request: RunRequest) -> RunRecord:
        """Execute and persist one run; returns the stored record."""
        pack, resolved = self.resolve(request)
        started = datetime.now(UTC)
        logger.info("run_id=%s pack=%s scenario=%s start", resolved.run_id, pack.pack_id,
                    resolved.scenario.scenario_id)  # fmt: skip
        try:
            output = pack.run(resolved)
        except Exception as exc:
            self._store.save(self._record(pack, resolved, started, RunStatus.FAILED, error=exc))
            logger.error("run_id=%s failed: %s", resolved.run_id, exc)
            raise
        record = self._record(pack, resolved, started, RunStatus.SUCCEEDED, output=output)
        self._store.save(record)
        logger.info("run_id=%s succeeded", resolved.run_id)
        return record

    def _record(
        self,
        pack: ScenarioPack,
        resolved: ResolvedRun,
        started: datetime,
        status: RunStatus,
        output: PackRunOutput | None = None,
        error: Exception | None = None,
    ) -> RunRecord:
        fields: dict[str, object] = {}
        if output is not None:
            fields = {
                "labels": output.labels,
                "variant_metrics": {
                    name: _totals(result) for name, result in output.comparison.variants.items()
                },
                "supporting_metrics": {
                    name: _totals(result) for name, result in output.supporting.items()
                },
                "inputs": {
                    name: self._store.store_dataset(dataset)
                    for name, dataset in output.inputs.items()
                },
                "outputs": self._outputs(output),
            }
        return RunRecord.model_validate(
            {
                "run_id": resolved.run_id,
                "status": status,
                "pack": pack.pack_id,
                "pack_version": pack.pack_version,
                "request": resolved.request,
                "scenario": resolved.scenario,
                "scenario_overrides": resolved.request.scenario_overrides,
                "created_at": started,
                "finished_at": datetime.now(UTC),
                "error": f"{type(error).__name__}: {error}" if error else None,
                **fields,
            }
        )

    def _outputs(self, output: PackRunOutput) -> dict[str, DatasetLink]:
        results = {**output.supporting, **output.comparison.variants}
        links = {}
        for name, result in results.items():
            if result.prediction is not None:
                links[f"{name}.prediction"] = self._store.store_dataset(result.prediction)
            for table, dataset in result.simulation_result.items():
                links[f"{name}.{table}"] = self._store.store_dataset(dataset)
        return links


def _totals(result: SimulationResult) -> dict[str, float | None]:
    return {m.metric_id: m.value for m in result.metrics if m.scope == "total"}
