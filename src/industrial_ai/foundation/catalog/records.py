"""SQLite tables of the dataset catalog (SQLModel).

Structured objects (schema, metadata, provenance) are stored as JSON produced by their pydantic
models, so the catalog stores exactly what the models validate and can re-validate on read.
"""

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class DatasetRecord(SQLModel, table=True):
    __tablename__ = "catalog_dataset"
    __table_args__ = (UniqueConstraint("dataset_id", "version"),)

    id: int | None = Field(default=None, primary_key=True)
    """Registration sequence; the latest version of a dataset is the highest id."""
    dataset_id: str = Field(index=True)
    version: str
    schema_id: str
    source_type: str = Field(index=True)
    row_count: int
    content_hash: str
    artifact_path: str
    """Parquet file path relative to the catalog's artifact root."""
    table_schema_json: str
    metadata_json: str
    provenance_json: str


class BundleRecord(SQLModel, table=True):
    __tablename__ = "catalog_bundle"
    __table_args__ = (UniqueConstraint("bundle_id", "version"),)

    id: int | None = Field(default=None, primary_key=True)
    bundle_id: str = Field(index=True)
    version: str
    content_hash: str
    tables_json: str
    """``{table_name: [dataset_id, version]}``."""
    source_json: str
    lineage_json: str


CATALOG_TABLES = [DatasetRecord.__table__, BundleRecord.__table__]  # type: ignore[attr-defined]
