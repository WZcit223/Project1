"""Provenance records (docs/synthetic-data-api.md §5).

A :class:`ProvenanceRecord` answers: source dataset → generator → version → parameters →
scenario → seed → transformations → output. :class:`Lineage` is the part supplied by whoever
produces an artifact; the output hash, timestamps and framework version are filled in when the
artifact is built, so they cannot be fabricated by the caller.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

ArtifactType = Literal["dataset", "bundle", "simulation_result"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class InputRef(_Frozen):
    """An input artifact, pinned by content hash."""

    dataset_id: str
    version: str
    content_hash: str


class ComponentRef(_Frozen):
    """A versioned component (generator, adapter, plugin) that produced the artifact."""

    id: str
    version: str


class ScenarioRef(_Frozen):
    scenario_id: str
    version: str
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class TransformationStep(_Frozen):
    """One recorded processing step, e.g. ``ingest``, ``unpivot``, ``calibrate``."""

    step: str
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ValidationRef(_Frozen):
    passed: bool
    report_id: str | None = None


class OutputRef(_Frozen):
    content_hash: str
    row_count: int = Field(ge=0)


class Lineage(_Frozen):
    """How an artifact was produced — supplied by the producer (loader, adapter, generator)."""

    inputs: tuple[InputRef, ...] = ()
    component: ComponentRef | None = None
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    scenario: ScenarioRef | None = None
    seed: int | None = None
    transformations: tuple[TransformationStep, ...] = ()
    validation: ValidationRef | None = None


class ProvenanceRecord(Lineage):
    """Complete, serialisable provenance of one artifact."""

    artifact_id: str
    artifact_type: ArtifactType
    created_at: datetime
    framework_version: str
    output: OutputRef
