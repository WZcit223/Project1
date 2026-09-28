"""Run request and run record models of the application layer (docs/application-api.md §3–4).

The framework part of a request is generic (pack, scenario, overrides, seed, horizon length);
everything domain-specific travels in ``options`` and is validated by the pack's own model.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from industrial_ai.scenario import ScenarioSpec


class RunRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pack: str
    scenario_id: str
    scenario_version: str | None = None
    """``None`` = latest registered version."""
    scenario_overrides: dict[str, JsonValue] = Field(default_factory=dict)
    """Per-run parameter changes, validated against the pack's scenario parameter model."""
    seed: int
    horizon_days: int = Field(ge=1)
    options: dict[str, JsonValue] = Field(default_factory=dict)
    """Pack-specific options (e.g. reference data, forecast model, strategies)."""


class RunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ResolvedRun(BaseModel):
    """A validated request as handed to a pack: effective scenario and typed options."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    run_id: str
    request: RunRequest
    scenario: ScenarioSpec
    """Registered scenario with the overrides merged into its parameters."""
    options: BaseModel


class DatasetLink(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    version: str
    content_hash: str


class RunRecord(BaseModel):
    """What a run did and produced; persisted by the run store."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    status: RunStatus
    pack: str
    pack_version: str
    request: RunRequest
    scenario: ScenarioSpec
    """Effective scenario (registered spec + overrides)."""
    scenario_overrides: dict[str, JsonValue]
    created_at: datetime
    finished_at: datetime
    error: str | None = None
    labels: tuple[str, ...] = ()
    """Maturity labels, e.g. ``prototype``, ``synthetic-data`` (docs/validation.md §1)."""
    variant_metrics: dict[str, dict[str, float | None]] = Field(default_factory=dict)
    """Total-scope metrics per compared variant (e.g. per strategy)."""
    supporting_metrics: dict[str, dict[str, float | None]] = Field(default_factory=dict)
    """Metrics of supporting runs (e.g. the forecast)."""
    inputs: dict[str, DatasetLink] = Field(default_factory=dict)
    """Datasets the run generated or used, registered in the catalog."""
    outputs: dict[str, DatasetLink] = Field(default_factory=dict)
    """Result tables, keyed ``<variant>.<table>`` or ``<supporting>.<table>``."""
