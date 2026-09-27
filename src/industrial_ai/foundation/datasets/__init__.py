"""Dataset abstraction: schema, metadata, Dataset and DatasetBundle (docs/data-model.md §1)."""

from industrial_ai.foundation.datasets.dataset import Dataset, DatasetBundle, build_dataset
from industrial_ai.foundation.datasets.metadata import (
    DatasetMetadata,
    SourceInfo,
    SourceType,
    TimeRange,
)
from industrial_ai.foundation.datasets.schema import DatasetSchema, DType, FieldSpec, ForeignKey

__all__ = [
    "DType",
    "Dataset",
    "DatasetBundle",
    "DatasetMetadata",
    "DatasetSchema",
    "FieldSpec",
    "ForeignKey",
    "SourceInfo",
    "SourceType",
    "TimeRange",
    "build_dataset",
]
