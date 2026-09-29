"""Run store: run records in SQLite, run datasets in the dataset catalog (docs/architecture.md §6).

A run record references every dataset it generated or used by ``(dataset_id, version,
content_hash)``; the datasets themselves (with their provenance) live in the catalog.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlmodel import Field, Session, SQLModel, col, select

from industrial_ai.application.models import DatasetLink, RunRecord
from industrial_ai.core.errors import DatasetAlreadyRegisteredError, RunNotFoundError
from industrial_ai.foundation.catalog import DatasetCatalog, create_database_engine
from industrial_ai.foundation.datasets import Dataset


class RunRow(SQLModel, table=True):
    __tablename__ = "application_run"

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, unique=True)
    pack: str = Field(index=True)
    scenario_id: str = Field(index=True)
    status: str
    created_at: datetime
    record_json: str


class RunStore:
    def __init__(self, database_url: str, catalog: DatasetCatalog) -> None:
        self._engine = create_database_engine(database_url)
        self._catalog = catalog
        SQLModel.metadata.create_all(self._engine, tables=[RunRow.__table__])  # type: ignore[attr-defined]

    @property
    def catalog(self) -> DatasetCatalog:
        return self._catalog

    def save(self, record: RunRecord) -> None:
        with self._session() as session:
            session.add(
                RunRow(
                    run_id=record.run_id,
                    pack=record.pack,
                    scenario_id=record.scenario.scenario_id,
                    status=record.status.value,
                    created_at=record.created_at,
                    record_json=record.model_dump_json(),
                )
            )
            session.commit()

    def get(self, run_id: str) -> RunRecord:
        with self._session() as session:
            row = session.exec(select(RunRow).where(RunRow.run_id == run_id)).first()
        if row is None:
            raise RunNotFoundError(f"no run {run_id!r}")
        return RunRecord.model_validate_json(row.record_json)

    def list(self) -> list[RunRecord]:
        """All runs, most recent first."""
        with self._session() as session:
            rows = session.exec(select(RunRow).order_by(col(RunRow.id).desc())).all()
        return [RunRecord.model_validate_json(row.record_json) for row in rows]

    def store_dataset(self, dataset: Dataset) -> DatasetLink:
        """Register ``dataset`` in the catalog, or reuse an identical registered copy.

        Raises:
            DatasetAlreadyRegisteredError: the same ``(dataset_id, version)`` exists with different
                content (ids must identify content; nothing is overwritten).
        """
        if self._catalog.contains(dataset.dataset_id, dataset.version):
            existing = self._catalog.summary(dataset.dataset_id, dataset.version)
            if existing.content_hash != dataset.metadata.content_hash:
                raise DatasetAlreadyRegisteredError(
                    f"{dataset.ref} is already registered with different content"
                )
        else:
            self._catalog.register(dataset)
        return DatasetLink(
            dataset_id=dataset.dataset_id,
            version=dataset.version,
            content_hash=dataset.metadata.content_hash,
        )

    @contextmanager
    def _session(self) -> Iterator[Session]:
        with Session(self._engine) as session:
            yield session
