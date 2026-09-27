"""Simulation plugin protocol and result model (docs/simulation-api.md §1–2).

Like synthetic generators, plugins return raw output (:class:`PluginOutput`); the
:class:`~industrial_ai.simulation.engine.SimulationEngine` turns it into a
:class:`SimulationResult` with provenance-carrying datasets, validated tables and run metadata.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

import pandas as pd
from pydantic import BaseModel, ConfigDict, JsonValue

from industrial_ai.core.errors import SimulationInputError
from industrial_ai.foundation.datasets import Dataset, DatasetBundle, DatasetSchema
from industrial_ai.foundation.validation import ConstraintSet
from industrial_ai.scenario import ScenarioSpec


class PluginKind(StrEnum):
    FORECAST = "forecast"
    SIMULATION = "simulation"
    STRATEGY_EVALUATION = "strategy_evaluation"
    OPTIMIZATION = "optimization"
    """Reserved (future): no v0.1 plugin."""
    CAUSAL = "causal"
    """Reserved (future): no v0.1 plugin."""


class Metric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_id: str
    value: float | None
    """``None`` when undefined (e.g. a ratio with a zero denominator) — never a made-up number."""
    unit: str = ""
    scope: str = "total"
    """``total`` or a sub-scope such as ``product:FOODS_3_001``."""


@dataclass(frozen=True)
class OutputTable:
    """A table produced by a plugin, with the schema it must satisfy."""

    schema: DatasetSchema
    data: pd.DataFrame


@dataclass(frozen=True)
class PluginOutput:
    """Raw output of a plugin run."""

    prediction: OutputTable | None = None
    tables: Mapping[str, OutputTable] = field(default_factory=dict)
    metrics: tuple[Metric, ...] = ()
    warnings: tuple[str, ...] = ()
    applied_scenario_parameters: frozenset[str] = frozenset()
    details: Mapping[str, JsonValue] = field(default_factory=dict)
    """Plugin-specific facts recorded in provenance (e.g. training rows, feature names)."""


@dataclass(frozen=True)
class RunContext:
    """What a plugin needs to know about the run it is part of."""

    run_id: str
    seed: int
    start_date: date
    """First day of the simulation horizon."""
    end_date: date
    """Last day of the simulation horizon (inclusive)."""
    upstream: Mapping[str, "SimulationResult"] = field(default_factory=dict)
    """Results of earlier steps, by name (e.g. ``"forecast"``)."""
    created_at: datetime | None = None
    """Timestamp for output datasets (``None`` = now); fixed values make metadata reproducible."""

    def with_upstream(self, name: str, result: "SimulationResult") -> "RunContext":
        return replace(self, upstream={**self.upstream, name: result})

    def require_upstream(self, name: str) -> "SimulationResult":
        try:
            return self.upstream[name]
        except KeyError:
            raise SimulationInputError(
                f"run {self.run_id}: upstream result {name!r} is required "
                f"(available: {sorted(self.upstream)})"
            ) from None


@runtime_checkable
class SimulationPlugin(Protocol):
    plugin_id: str
    plugin_version: str
    kind: PluginKind
    description: str
    parameter_model: type[BaseModel]
    required_inputs: tuple[str, ...]
    """Schema ids the input dataset (or bundle) must contain, e.g. ``("retail.sales",)``."""

    def run(
        self,
        dataset: Dataset | DatasetBundle,
        scenario: ScenarioSpec | None,
        parameters: BaseModel,
        constraints: ConstraintSet,
        context: RunContext,
    ) -> PluginOutput:
        """Run the plugin. All randomness must come from ``context.seed``."""
        ...


class ScenarioResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str | None
    scenario_version: str | None
    applied_parameters: dict[str, JsonValue]


class RunMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin_id: str
    plugin_version: str
    kind: PluginKind
    run_id: str
    seed: int
    parameters: dict[str, JsonValue]
    input_hashes: dict[str, str]
    """Input dataset id → content hash."""
    started_at: datetime
    finished_at: datetime
    status: str = "succeeded"
    """Always ``succeeded``: failed runs raise instead of returning a result."""
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SimulationResult:
    prediction: Dataset | None
    simulation_result: Mapping[str, Dataset]
    scenario_result: ScenarioResult
    metrics: tuple[Metric, ...]
    metadata: RunMetadata

    def metric(self, metric_id: str, scope: str = "total") -> Metric:
        for m in self.metrics:
            if m.metric_id == metric_id and m.scope == scope:
                return m
        raise KeyError(f"no metric {metric_id!r} with scope {scope!r}")

    def table(self, name: str) -> Dataset:
        try:
            return self.simulation_result[name]
        except KeyError:
            raise KeyError(
                f"no result table {name!r} (tables: {sorted(self.simulation_result)})"
            ) from None


class PluginInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    plugin_id: str
    plugin_version: str
    kind: PluginKind
    description: str
    required_inputs: tuple[str, ...]
    parameter_schema: dict[str, JsonValue]
