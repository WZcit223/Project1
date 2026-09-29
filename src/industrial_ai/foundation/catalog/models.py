"""Read models returned by the catalog (JSON-safe, for the API and UI)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, JsonValue

from industrial_ai.foundation.datasets import SourceType


class DatasetSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset_id: str
    version: str
    name: str
    schema_id: str
    source_type: SourceType
    row_count: int
    content_hash: str
    created_at: datetime


class ColumnSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    dtype: str
    null_count: int
    min: JsonValue = None
    max: JsonValue = None
    mean: float | None = None


class DatasetPreview(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset: DatasetSummary
    columns: tuple[ColumnSummary, ...]
    rows: list[dict[str, JsonValue]]
    """First ``limit`` rows, JSON-safe (dates as ISO strings)."""
