"""Dataset metadata (docs/data-model.md §1.4)."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SourceType(StrEnum):
    REFERENCE = "reference"
    """Real external data, e.g. M5."""
    SYNTHETIC = "synthetic"
    DERIVED = "derived"
    FIXTURE = "fixture"
    """Small synthetic data committed for tests."""


class TimeRange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    start: datetime
    end: datetime


class SourceInfo(BaseModel):
    """Descriptive metadata supplied by the producer of a dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str = ""
    source_type: SourceType
    source: str | None = None
    source_url: str | None = None
    dataset_version: str | None = None
    download_date: date | None = None
    license_notes: str | None = None
    tags: tuple[str, ...] = ()


class DatasetMetadata(SourceInfo):
    """Complete metadata: the producer's :class:`SourceInfo` plus values computed from the data."""

    row_count: int = Field(ge=0)
    content_hash: str
    created_at: datetime
    time_range: TimeRange | None = None
    entity_counts: dict[str, int] = Field(default_factory=dict)
    """Number of distinct values per entity key (e.g. ``{"product_id": 50}``)."""
