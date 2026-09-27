"""Simulation engine: runs registered plugins and compares variants (docs/simulation-api.md §3).

For every run the engine checks the plugin's required inputs, validates parameters, calls the
plugin, turns its tables into datasets with provenance (inputs pinned by hash, plugin, parameters,
scenario, seed), validates them against their schemas and records run metadata. A failure at any
step raises; there is no "failed" result object that could be mistaken for a real one.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime

import pandas as pd
from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from industrial_ai.core.errors import SimulationError, SimulationInputError
from industrial_ai.foundation.datasets import (
    Dataset,
    DatasetBundle,
    SourceInfo,
    SourceType,
    build_dataset,
)
from industrial_ai.foundation.provenance import (
    ComponentRef,
    InputRef,
    Lineage,
    ScenarioRef,
    TransformationStep,
)
from industrial_ai.foundation.validation import ConstraintSet, validate_dataset
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.simulation.base import (
    OutputTable,
    PluginOutput,
    RunContext,
    RunMetadata,
    ScenarioResult,
    SimulationPlugin,
    SimulationResult,
)
from industrial_ai.simulation.registry import SimulationRegistry


class ComparisonResult(BaseModel):
    """Results of one plugin run under several parameter variants (same data, scenario, seed)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    plugin_id: str
    variants: dict[str, SimulationResult]

    def metrics_table(self, scope: str = "total") -> pd.DataFrame:
        """Variants as rows, metric ids as columns (values; ``None`` stays missing)."""
        rows = {
            name: {m.metric_id: m.value for m in result.metrics if m.scope == scope}
            for name, result in self.variants.items()
        }
        return pd.DataFrame.from_dict(rows, orient="index")


class SimulationEngine:
    def __init__(self, registry: SimulationRegistry) -> None:
        self._registry = registry

    def run(
        self,
        plugin_id: str,
        dataset: Dataset | DatasetBundle,
        scenario: ScenarioSpec | None,
        parameters: Mapping[str, JsonValue],
        context: RunContext,
        constraints: ConstraintSet | None = None,
        version: str | None = None,
    ) -> SimulationResult:
        """Run one plugin.

        Raises:
            PluginNotFoundError: unknown plugin / version.
            SimulationInputError: missing required inputs or invalid parameters.
            SimulationError: invalid plugin output.
        """
        plugin = self._registry.get(plugin_id, version)
        _check_inputs(plugin, dataset)
        params = _validated(plugin, parameters)
        started = datetime.now(UTC)
        output = plugin.run(dataset, scenario, params, constraints or ConstraintSet(), context)
        finished = datetime.now(UTC)
        warnings = (*output.warnings, *_unused(plugin, scenario, output))
        param_dump = params.model_dump(mode="json")
        lineage = Lineage(
            inputs=_input_refs(dataset, context),
            component=ComponentRef(id=plugin.plugin_id, version=plugin.plugin_version),
            parameters=param_dump,
            scenario=_scenario_ref(scenario),
            seed=context.seed,
            transformations=(
                TransformationStep(
                    step="simulate",
                    details={
                        "kind": plugin.kind.value,
                        "run_id": context.run_id,
                        "horizon": [context.start_date.isoformat(), context.end_date.isoformat()],
                        "upstream": list[JsonValue](sorted(context.upstream)),
                        "warnings": list[JsonValue](warnings),
                    },
                ),
            ),
        )

        def build(name: str, table: OutputTable) -> Dataset:
            result = build_dataset(
                dataset_id=f"{context.run_id}.{plugin.plugin_id}.{name}",
                version="1",
                schema=table.schema,
                data=table.data,
                source=SourceInfo(
                    name=f"{plugin.plugin_id} {name} ({context.run_id})",
                    source_type=SourceType.DERIVED,
                    tags=("simulation", plugin.kind.value),
                ),
                lineage=lineage,
                created_at=context.created_at,
            )
            report = validate_dataset(result)
            if not report.passed:
                raise SimulationError(
                    f"{plugin.plugin_id}: output table {name!r} failed validation: "
                    + "; ".join(
                        f"{f.check} {f.target} ({f.violations})" for f in report.failures[:5]
                    )
                )
            return result

        prediction = build("prediction", output.prediction) if output.prediction else None
        tables = {name: build(name, table) for name, table in output.tables.items()}
        return SimulationResult(
            prediction=prediction,
            simulation_result=tables,
            scenario_result=ScenarioResult(
                scenario_id=scenario.scenario_id if scenario else None,
                scenario_version=scenario.version if scenario else None,
                applied_parameters={
                    k: v
                    for k, v in (scenario.parameters.items() if scenario else [])
                    if k in output.applied_scenario_parameters
                },
            ),
            metrics=output.metrics,
            metadata=RunMetadata(
                plugin_id=plugin.plugin_id,
                plugin_version=plugin.plugin_version,
                kind=plugin.kind,
                run_id=context.run_id,
                seed=context.seed,
                parameters=param_dump,
                input_hashes={ref.dataset_id: ref.content_hash for ref in lineage.inputs},
                started_at=started,
                finished_at=finished,
                warnings=tuple(warnings),
            ),
        )

    def compare(
        self,
        plugin_id: str,
        dataset: Dataset | DatasetBundle,
        scenario: ScenarioSpec | None,
        variants: Mapping[str, Mapping[str, JsonValue]],
        context: RunContext,
        constraints: ConstraintSet | None = None,
        version: str | None = None,
    ) -> ComparisonResult:
        """Run the same plugin on the same data, scenario and seed with different parameters."""
        if not variants:
            raise SimulationInputError("compare() needs at least one variant")
        results = {
            name: self.run(
                plugin_id,
                dataset,
                scenario,
                params,
                replace(context, run_id=f"{context.run_id}.{name}"),
                constraints,
                version,
            )
            for name, params in variants.items()
        }
        return ComparisonResult(plugin_id=plugin_id, variants=results)


def _check_inputs(plugin: SimulationPlugin, dataset: Dataset | DatasetBundle) -> None:
    available = (
        {dataset.schema.schema_id}
        if isinstance(dataset, Dataset)
        else {t.schema.schema_id for t in dataset.tables.values()}
    )
    missing = sorted(set(plugin.required_inputs) - available)
    if missing:
        raise SimulationInputError(
            f"{plugin.plugin_id} needs inputs {missing}; available: {sorted(available)}"
        )


def _validated(plugin: SimulationPlugin, parameters: Mapping[str, JsonValue]) -> BaseModel:
    try:
        return plugin.parameter_model.model_validate(dict(parameters))
    except ValidationError as exc:
        raise SimulationInputError(
            f"invalid parameters for {plugin.plugin_id}@{plugin.plugin_version}: {exc}"
        ) from exc


def _unused(
    plugin: SimulationPlugin, scenario: ScenarioSpec | None, output: PluginOutput
) -> list[str]:
    if scenario is None:
        return []
    unused = sorted(set(scenario.parameters) - output.applied_scenario_parameters)
    if not unused:
        return []
    return [
        f"scenario {scenario.scenario_id!r} parameters not applied by {plugin.plugin_id}: {unused}"
    ]


def _input_refs(dataset: Dataset | DatasetBundle, context: RunContext) -> tuple[InputRef, ...]:
    """Input datasets plus all upstream result tables, in a stable order."""
    tables: list[Dataset] = (
        [dataset]
        if isinstance(dataset, Dataset)
        else [dataset.tables[n] for n in sorted(dataset.tables)]
    )
    for name in sorted(context.upstream):
        result = context.upstream[name]
        if result.prediction is not None:
            tables.append(result.prediction)
        tables.extend(result.simulation_result[t] for t in sorted(result.simulation_result))
    return tuple(d.as_input() for d in tables)


def _scenario_ref(scenario: ScenarioSpec | None) -> ScenarioRef | None:
    if scenario is None:
        return None
    return ScenarioRef(
        scenario_id=scenario.scenario_id, version=scenario.version, parameters=scenario.parameters
    )
