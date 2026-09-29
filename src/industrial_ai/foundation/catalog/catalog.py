"""Dataset catalog: SQLite metadata + Parquet artifacts (docs/architecture.md §6).

- ``register`` writes the data to Parquet, reads it back and checks the content hash before the
  catalog entry is committed, so a registered dataset is guaranteed to reload identically.
- ``get`` rebuilds the :class:`Dataset`, whose constructor re-verifies the content hash: a
  modified artifact file is detected instead of being served.
- Dataset versions are free-form strings; "latest" means most recently registered.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
from pydantic import JsonValue, TypeAdapter
from sqlalchemy import Engine, make_url
from sqlmodel import Session, SQLModel, col, create_engine, select

from industrial_ai.core.config import Settings
from industrial_ai.core.errors import (
    DatasetAlreadyRegisteredError,
    DatasetError,
    DatasetNotFoundError,
)
from industrial_ai.foundation.catalog.models import ColumnSummary, DatasetPreview, DatasetSummary
from industrial_ai.foundation.catalog.records import CATALOG_TABLES, BundleRecord, DatasetRecord
from industrial_ai.foundation.datasets import (
    Dataset,
    DatasetBundle,
    DatasetMetadata,
    DatasetSchema,
    SourceInfo,
    SourceType,
)
from industrial_ai.foundation.provenance import Lineage, ProvenanceRecord, content_hash

_TABLE_REFS = TypeAdapter(dict[str, tuple[str, str]])


class DatasetCatalog:
    """Registry of datasets and bundles, persisted in SQLite with Parquet artifacts."""

    def __init__(self, database_url: str, artifact_root: Path) -> None:
        self._artifact_root = artifact_root
        self._engine = create_database_engine(database_url)
        SQLModel.metadata.create_all(self._engine, tables=CATALOG_TABLES)

    @classmethod
    def from_settings(cls, settings: Settings) -> "DatasetCatalog":
        return cls(settings.database_url, settings.data_dir / "processed" / "artifacts")

    @property
    def artifact_root(self) -> Path:
        return self._artifact_root

    # --- datasets ---------------------------------------------------------------------------

    def register(self, dataset: Dataset) -> DatasetSummary:
        """Persist a dataset.

        Raises:
            DatasetAlreadyRegisteredError: if ``(dataset_id, version)`` exists.
            DatasetError: if the data does not survive the Parquet round trip unchanged.
        """
        with self._session() as session:
            if self._find(session, dataset.dataset_id, dataset.version) is not None:
                raise DatasetAlreadyRegisteredError(f"{dataset.ref} is already registered")
            relative = Path("datasets") / dataset.dataset_id / dataset.version / "data.parquet"
            self._write_verified(dataset, self._artifact_root / relative)
            record = DatasetRecord(
                dataset_id=dataset.dataset_id,
                version=dataset.version,
                schema_id=dataset.schema.schema_id,
                source_type=dataset.metadata.source_type.value,
                row_count=dataset.metadata.row_count,
                content_hash=dataset.metadata.content_hash,
                artifact_path=relative.as_posix(),
                table_schema_json=dataset.schema.model_dump_json(),
                metadata_json=dataset.metadata.model_dump_json(),
                provenance_json=dataset.provenance.model_dump_json(),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return _summary(record)

    def get(self, dataset_id: str, version: str | None = None) -> Dataset:
        """Load a dataset (latest registered version if ``version`` is omitted).

        Raises:
            DatasetNotFoundError: if it is not registered.
            DatasetError: if the stored artifact no longer matches its recorded content hash.
        """
        with self._session() as session:
            record = self._require(session, dataset_id, version)
        data = pd.read_parquet(self._artifact_root / record.artifact_path)
        return Dataset(
            dataset_id=record.dataset_id,
            version=record.version,
            schema=DatasetSchema.model_validate_json(record.table_schema_json),
            data=data,
            metadata=DatasetMetadata.model_validate_json(record.metadata_json),
            provenance=ProvenanceRecord.model_validate_json(record.provenance_json),
        )

    def summary(self, dataset_id: str, version: str | None = None) -> DatasetSummary:
        """Catalog entry without loading the data (latest version if ``version`` is omitted).

        Raises:
            DatasetNotFoundError: if it is not registered.
        """
        with self._session() as session:
            return _summary(self._require(session, dataset_id, version))

    def contains(self, dataset_id: str, version: str | None = None) -> bool:
        with self._session() as session:
            return self._find(session, dataset_id, version) is not None

    def list(self, source_type: SourceType | None = None) -> list[DatasetSummary]:
        """All registered datasets in registration order, optionally filtered by source type."""
        with self._session() as session:
            query = select(DatasetRecord).order_by(col(DatasetRecord.id))
            if source_type is not None:
                query = query.where(DatasetRecord.source_type == source_type.value)
            return [_summary(record) for record in session.exec(query)]

    def preview(
        self, dataset_id: str, version: str | None = None, limit: int = 50
    ) -> DatasetPreview:
        """Summary, per-column statistics and the first ``limit`` rows (JSON-safe)."""
        if limit < 0:
            raise ValueError("limit must be >= 0")
        dataset = self.get(dataset_id, version)
        with self._session() as session:
            summary = _summary(self._require(session, dataset.dataset_id, dataset.version))
        head = dataset.data.head(limit)
        rows = json.loads(head.to_json(orient="records", date_format="iso")) if limit else []
        columns = tuple(_column_summary(name, dataset.data[name]) for name in dataset.data.columns)
        return DatasetPreview(dataset=summary, columns=columns, rows=rows)

    # --- bundles ----------------------------------------------------------------------------

    def register_bundle(self, bundle: DatasetBundle) -> None:
        """Persist a bundle. Member tables are registered unless already registered identically.

        Raises:
            DatasetAlreadyRegisteredError: if the bundle id/version exists, or a member table's
                ``(dataset_id, version)`` exists with different content.
        """
        with self._session() as session:
            if self._find_bundle(session, bundle.bundle_id, bundle.version) is not None:
                raise DatasetAlreadyRegisteredError(f"bundle {bundle.ref} is already registered")
            for table in bundle.tables.values():
                existing = self._find(session, table.dataset_id, table.version)
                if existing is not None and existing.content_hash != table.metadata.content_hash:
                    raise DatasetAlreadyRegisteredError(
                        f"{table.ref} is registered with different content"
                    )
        for table in bundle.tables.values():
            if not self.contains(table.dataset_id, table.version):
                self.register(table)
        refs = {name: (t.dataset_id, t.version) for name, t in bundle.tables.items()}
        with self._session() as session:
            session.add(
                BundleRecord(
                    bundle_id=bundle.bundle_id,
                    version=bundle.version,
                    content_hash=bundle.content_hash,
                    tables_json=json.dumps(refs, sort_keys=True),
                    source_json=bundle.source.model_dump_json(),
                    lineage_json=bundle.lineage.model_dump_json(),
                )
            )
            session.commit()

    def get_bundle(self, bundle_id: str, version: str | None = None) -> DatasetBundle:
        """Load a bundle and its member tables (latest registered version if omitted)."""
        with self._session() as session:
            record = self._find_bundle(session, bundle_id, version)
            if record is None:
                raise DatasetNotFoundError(_missing("bundle", bundle_id, version))
        refs = _TABLE_REFS.validate_json(record.tables_json)
        tables = {name: self.get(ds_id, ds_version) for name, (ds_id, ds_version) in refs.items()}
        bundle = DatasetBundle(
            bundle_id=record.bundle_id,
            version=record.version,
            tables=tables,
            source=SourceInfo.model_validate_json(record.source_json),
            lineage=Lineage.model_validate_json(record.lineage_json),
        )
        if bundle.content_hash != record.content_hash:
            raise DatasetError(f"bundle {bundle.ref}: member tables changed since registration")
        return bundle

    # --- internals --------------------------------------------------------------------------

    @contextmanager
    def _session(self) -> Iterator[Session]:
        with Session(self._engine) as session:
            yield session

    @staticmethod
    def _find(session: Session, dataset_id: str, version: str | None) -> DatasetRecord | None:
        query = select(DatasetRecord).where(DatasetRecord.dataset_id == dataset_id)
        if version is not None:
            query = query.where(DatasetRecord.version == version)
        return session.exec(query.order_by(col(DatasetRecord.id).desc())).first()

    def _require(self, session: Session, dataset_id: str, version: str | None) -> DatasetRecord:
        record = self._find(session, dataset_id, version)
        if record is None:
            raise DatasetNotFoundError(_missing("dataset", dataset_id, version))
        return record

    @staticmethod
    def _find_bundle(session: Session, bundle_id: str, version: str | None) -> BundleRecord | None:
        query = select(BundleRecord).where(BundleRecord.bundle_id == bundle_id)
        if version is not None:
            query = query.where(BundleRecord.version == version)
        return session.exec(query.order_by(col(BundleRecord.id).desc())).first()

    @staticmethod
    def _write_verified(dataset: Dataset, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".parquet.tmp")
        dataset.data.to_parquet(tmp, index=False)
        if content_hash(pd.read_parquet(tmp)) != dataset.metadata.content_hash:
            tmp.unlink()
            raise DatasetError(f"{dataset.ref}: data changes in a Parquet round trip")
        tmp.replace(path)


def create_database_engine(database_url: str) -> Engine:
    """SQLAlchemy engine; creates the directory of a file-based SQLite database."""
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(database_url)


def _missing(kind: str, identifier: str, version: str | None) -> str:
    suffix = f" version {version}" if version is not None else ""
    return f"no {kind} {identifier!r}{suffix} in the catalog"


def _summary(record: DatasetRecord) -> DatasetSummary:
    metadata = DatasetMetadata.model_validate_json(record.metadata_json)
    return DatasetSummary(
        dataset_id=record.dataset_id,
        version=record.version,
        name=metadata.name,
        schema_id=record.schema_id,
        source_type=metadata.source_type,
        row_count=record.row_count,
        content_hash=record.content_hash,
        created_at=metadata.created_at,
    )


def _column_summary(name: str, series: pd.Series) -> ColumnSummary:
    non_null = series.dropna()
    numeric = pd.api.types.is_numeric_dtype(series.dtype) and not pd.api.types.is_bool_dtype(
        series.dtype
    )
    low: JsonValue = None
    high: JsonValue = None
    if len(non_null) and numeric:
        low, high = non_null.min().item(), non_null.max().item()
    elif len(non_null) and pd.api.types.is_datetime64_any_dtype(series.dtype):
        low, high = non_null.min().isoformat(), non_null.max().isoformat()
    return ColumnSummary(
        name=str(name),
        dtype=str(series.dtype),
        null_count=int(series.isna().sum()),
        min=low,
        max=high,
        mean=float(non_null.mean()) if numeric and len(non_null) else None,
    )
