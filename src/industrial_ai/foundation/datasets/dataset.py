"""Dataset containers (docs/data-model.md §1.3).

A :class:`Dataset` is built with :func:`build_dataset`, which derives every computable field
(row count, content hash, time range, entity counts, provenance output) from the data itself.
The constructor re-checks these invariants, so a Dataset cannot carry metadata or provenance
that disagrees with its data.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd

from industrial_ai import __version__
from industrial_ai.core.errors import DatasetError
from industrial_ai.foundation.datasets.metadata import DatasetMetadata, SourceInfo, TimeRange
from industrial_ai.foundation.datasets.schema import DatasetSchema
from industrial_ai.foundation.provenance import (
    InputRef,
    Lineage,
    OutputRef,
    ProvenanceRecord,
    content_hash,
    file_hash,
)


@dataclass(frozen=True)
class Dataset:
    """One table: data + schema + metadata + provenance."""

    dataset_id: str
    version: str
    schema: DatasetSchema
    data: pd.DataFrame = field(repr=False)
    metadata: DatasetMetadata
    provenance: ProvenanceRecord

    def __post_init__(self) -> None:
        if tuple(self.data.columns) != self.schema.field_names:
            raise DatasetError(
                f"{self.ref}: columns {list(self.data.columns)} do not match schema "
                f"{self.schema.schema_id} fields {list(self.schema.field_names)}"
            )
        if self.metadata.row_count != len(self.data):
            raise DatasetError(f"{self.ref}: metadata row_count does not match the data")
        if self.provenance.output.content_hash != self.metadata.content_hash:
            raise DatasetError(f"{self.ref}: provenance and metadata content hashes differ")
        if content_hash(self.data) != self.metadata.content_hash:
            raise DatasetError(f"{self.ref}: content hash does not match the data")

    @property
    def ref(self) -> str:
        return f"{self.dataset_id}@{self.version}"

    def as_input(self) -> InputRef:
        """Reference to this dataset for another artifact's provenance."""
        return InputRef(
            dataset_id=self.dataset_id,
            version=self.version,
            content_hash=self.metadata.content_hash,
        )


def build_dataset(
    *,
    dataset_id: str,
    version: str,
    schema: DatasetSchema,
    data: pd.DataFrame,
    source: SourceInfo,
    lineage: Lineage,
    created_at: datetime | None = None,
) -> Dataset:
    """Build a :class:`Dataset`, computing metadata and provenance from the data.

    Columns must be exactly the schema's fields (any order); they are reordered to schema order.
    The index is reset. Values are **not** validated here — use
    :func:`industrial_ai.foundation.validation.validate_dataset`.

    Raises:
        DatasetError: if the columns do not match the schema.
    """
    missing = sorted(set(schema.field_names) - set(data.columns))
    extra = sorted(set(map(str, data.columns)) - set(schema.field_names))
    if missing or extra:
        raise DatasetError(
            f"{dataset_id}@{version}: columns do not match schema {schema.schema_id} "
            f"(missing {missing}, unexpected {extra})"
        )
    frame = data.loc[:, list(schema.field_names)].reset_index(drop=True)
    timestamp = created_at or datetime.now(UTC)
    digest = content_hash(frame)
    metadata = DatasetMetadata(
        **source.model_dump(),
        row_count=len(frame),
        content_hash=digest,
        created_at=timestamp,
        time_range=_time_range(frame, schema),
        entity_counts={key: int(frame[key].nunique()) for key in schema.entity_keys},
    )
    provenance = ProvenanceRecord(
        **lineage.model_dump(),
        artifact_id=f"{dataset_id}@{version}",
        artifact_type="dataset",
        created_at=timestamp,
        framework_version=__version__,
        output=OutputRef(content_hash=digest, row_count=len(frame)),
    )
    return Dataset(dataset_id, version, schema, frame, metadata, provenance)


def _time_range(frame: pd.DataFrame, schema: DatasetSchema) -> TimeRange | None:
    if schema.time_index is None or frame.empty:
        return None
    times = pd.to_datetime(frame[schema.time_index])
    if times.isna().all():
        return None
    return TimeRange(start=times.min().to_pydatetime(), end=times.max().to_pydatetime())


@dataclass(frozen=True)
class DatasetBundle:
    """A logical dataset made of several named tables, e.g. sales + prices + calendar."""

    bundle_id: str
    version: str
    tables: Mapping[str, Dataset]
    source: SourceInfo
    lineage: Lineage = field(default_factory=Lineage)

    def __post_init__(self) -> None:
        if not self.tables:
            raise DatasetError(f"bundle {self.bundle_id}@{self.version} has no tables")

    @property
    def ref(self) -> str:
        return f"{self.bundle_id}@{self.version}"

    @property
    def content_hash(self) -> str:
        """Hash over the member tables' names and content hashes (order-independent)."""
        members = "\n".join(
            f"{name}={self.tables[name].metadata.content_hash}" for name in sorted(self.tables)
        )
        return file_hash(members.encode())

    def table(self, name: str) -> Dataset:
        try:
            return self.tables[name]
        except KeyError:
            raise DatasetError(
                f"bundle {self.ref} has no table {name!r} (tables: {sorted(self.tables)})"
            ) from None

    def by_schema(self, schema_id: str) -> Dataset:
        """The table whose schema is ``schema_id``."""
        matches = [d for d in self.tables.values() if d.schema.schema_id == schema_id]
        if len(matches) != 1:
            raise DatasetError(
                f"bundle {self.ref} has {len(matches)} tables with schema {schema_id!r}"
            )
        return matches[0]
