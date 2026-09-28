"""Read and write models the application service exposes to the API (docs/application-api.md)."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from industrial_ai.application.models import RunStatus
from industrial_ai.foundation.catalog import DatasetSummary
from industrial_ai.foundation.datasets import DatasetMetadata, DatasetSchema
from industrial_ai.foundation.provenance import ProvenanceRecord
from industrial_ai.scenario import ScenarioSpec


class PackInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    pack_id: str
    pack_version: str
    title: str
    description: str
    requires_reference: bool
    scenario_ids: tuple[str, ...]


class ReferenceInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    reference_id: str
    available: bool
    """Whether the configured directory exists on this server."""


class DatasetDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: DatasetSummary
    table_schema: DatasetSchema
    metadata: DatasetMetadata
    provenance: ProvenanceRecord


class ScenarioDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    spec: ScenarioSpec
    effective_parameters: dict[str, JsonValue]
    """The spec's parameters plus the pack's defaults."""
    parameter_schema: dict[str, JsonValue]
    """JSON schema of the pack's scenario parameter model."""


class RunCreate(BaseModel):
    """``POST /api/runs`` body: like ``RunRequest`` but with a reference *id* instead of a path."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pack: str
    reference_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    """Identifier of a configured reference dataset (e.g. ``m5_subset``) — never a file path; the
    server resolves it via ``IAI_REFERENCE_DIRS``."""
    scenario_id: str
    scenario_version: str | None = None
    scenario_overrides: dict[str, JsonValue] = Field(default_factory=dict)
    seed: int
    horizon_days: int = Field(ge=1, le=366)
    options: dict[str, JsonValue] = Field(default_factory=dict)


class RunSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    status: RunStatus
    pack: str
    scenario_id: str
    scenario_version: str
    seed: int
    created_at: str
    error: str | None


class RunResults(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    status: RunStatus
    scenario: ScenarioSpec
    labels: tuple[str, ...]
    variants: dict[str, dict[str, float | None]]
    """Total-scope metrics per compared variant (strategy)."""
    supporting: dict[str, dict[str, float | None]]
    metric_ids: tuple[str, ...]
    """Metric ids in a stable order (rows of the comparison table)."""


class TimePoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    value: float


class TimeSeries(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    variant: str
    table: str
    column: str
    filter: dict[str, str]
    aggregation: str
    points: tuple[TimePoint, ...]


class ComparisonRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    scenario_id: str
    scenario_version: str
    variant: str
    metrics: dict[str, float | None]
