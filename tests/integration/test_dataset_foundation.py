"""Integration test for Gate 2: a dataset can be loaded, validated, registered and reloaded.

File → load_table → validate_dataset → DatasetCatalog.register → new catalog instance → get,
with the content hash and provenance unchanged end to end.
"""

from pathlib import Path

from industrial_ai.foundation.catalog import DatasetCatalog
from industrial_ai.foundation.datasets import (
    DatasetSchema,
    DType,
    FieldSpec,
    SourceInfo,
    SourceType,
)
from industrial_ai.foundation.ingestion import load_table
from industrial_ai.foundation.validation import RangeConstraint, validate_dataset

SCHEMA = DatasetSchema(
    schema_id="it.demand",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="date", dtype=DType.DATE),
        FieldSpec(name="item_id", dtype=DType.STR),
        FieldSpec(name="quantity", dtype=DType.INT, min=0, unit="units"),
    ),
    primary_key=("date", "item_id"),
    time_index="date",
    entity_keys=("item_id",),
)

CSV = "date,item_id,quantity\n2016-01-01,X,4\n2016-01-01,Y,0\n2016-01-02,X,2\n2016-01-02,Y,7\n"


def test_file_to_catalog_and_back(tmp_path: Path) -> None:
    source_file = tmp_path / "demand.csv"
    source_file.write_text(CSV, encoding="utf-8")
    source = SourceInfo(
        name="Integration demand sample",
        source_type=SourceType.FIXTURE,
        license_notes="Synthetic test data",
    )

    dataset = load_table(source_file, SCHEMA, dataset_id="demand", version="1", source=source)
    report = validate_dataset(dataset, [RangeConstraint(field="quantity", max=100)])
    assert report.passed, report.failures

    db = f"sqlite:///{tmp_path / 'catalog.sqlite'}"
    DatasetCatalog(db, tmp_path / "artifacts").register(dataset)

    reloaded = DatasetCatalog(db, tmp_path / "artifacts").get("demand", "1")
    assert reloaded.metadata.content_hash == dataset.metadata.content_hash
    assert reloaded.provenance == dataset.provenance
    assert reloaded.metadata.entity_counts == {"item_id": 2}
    assert validate_dataset(reloaded).passed
