"""Tests for industrial_ai.foundation.catalog (SQLite + Parquet)."""

import subprocess
import sys
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from industrial_ai.core.config import load_settings
from industrial_ai.core.errors import (
    DatasetAlreadyRegisteredError,
    DatasetError,
    DatasetNotFoundError,
)
from industrial_ai.foundation.catalog import DatasetCatalog
from industrial_ai.foundation.datasets import DatasetBundle, SourceType

from .builders import SOURCE, make_products, make_sales, sales_frame


@pytest.fixture
def catalog(tmp_path: Path) -> DatasetCatalog:
    return DatasetCatalog(f"sqlite:///{tmp_path / 'db' / 'catalog.sqlite'}", tmp_path / "artifacts")


def test_register_and_get_round_trip(catalog: DatasetCatalog) -> None:
    original = make_sales()
    summary = catalog.register(original)
    assert summary.dataset_id == "sales" and summary.row_count == 4
    loaded = catalog.get("sales", "1")
    assert loaded.metadata == original.metadata
    assert loaded.provenance == original.provenance
    assert loaded.schema == original.schema
    assert loaded.metadata.content_hash == original.metadata.content_hash


def test_latest_version_is_most_recently_registered(catalog: DatasetCatalog) -> None:
    catalog.register(make_sales(version="2"))
    catalog.register(make_sales(sales_frame().assign(quantity=[1, 1, 1, 1]), version="10"))
    assert catalog.get("sales").version == "10"
    assert catalog.get("sales", "2").version == "2"


def test_duplicate_registration_is_rejected(catalog: DatasetCatalog) -> None:
    catalog.register(make_sales())
    with pytest.raises(DatasetAlreadyRegisteredError):
        catalog.register(make_sales())


def test_missing_dataset_raises(catalog: DatasetCatalog) -> None:
    with pytest.raises(DatasetNotFoundError):
        catalog.get("nope")
    catalog.register(make_sales())
    with pytest.raises(DatasetNotFoundError, match="version 9"):
        catalog.get("sales", "9")
    assert catalog.contains("sales") and not catalog.contains("sales", "9")


def test_tampered_artifact_is_detected(catalog: DatasetCatalog) -> None:
    catalog.register(make_sales())
    path = catalog.artifact_root / "datasets" / "sales" / "1" / "data.parquet"
    pd.read_parquet(path).assign(quantity=[9, 9, 9, 9]).to_parquet(path, index=False)
    with pytest.raises(DatasetError, match="content hash"):
        catalog.get("sales")


def test_list_filters_by_source_type(catalog: DatasetCatalog) -> None:
    catalog.register(make_sales())
    catalog.register(make_products())
    assert [s.dataset_id for s in catalog.list()] == ["sales", "products"]
    assert len(catalog.list(SourceType.FIXTURE)) == 2
    assert catalog.list(SourceType.REFERENCE) == []


def test_preview_is_json_safe(catalog: DatasetCatalog) -> None:
    catalog.register(make_sales())
    preview = catalog.preview("sales", limit=2)
    assert len(preview.rows) == 2
    assert preview.rows[0]["date"] == "2016-01-01T00:00:00.000"
    quantity = next(c for c in preview.columns if c.name == "quantity")
    assert (quantity.min, quantity.max, quantity.mean) == (0, 5, 2.25)
    price = next(c for c in preview.columns if c.name == "unit_price")
    assert price.null_count == 1
    date = next(c for c in preview.columns if c.name == "date")
    assert date.min == "2016-01-01T00:00:00"
    assert preview.model_dump_json()  # serialisable
    assert catalog.preview("sales", limit=0).rows == []


def test_bundle_round_trip_reuses_identical_tables(catalog: DatasetCatalog) -> None:
    catalog.register(make_products())  # already registered, identical: reused
    bundle = DatasetBundle(
        "retail", "1", {"sales": make_sales(), "products": make_products()}, SOURCE
    )
    catalog.register_bundle(bundle)
    loaded = catalog.get_bundle("retail")
    assert set(loaded.tables) == {"sales", "products"}
    assert loaded.content_hash == bundle.content_hash
    with pytest.raises(DatasetAlreadyRegisteredError):
        catalog.register_bundle(bundle)


def test_bundle_with_conflicting_table_is_rejected(catalog: DatasetCatalog) -> None:
    catalog.register(make_sales(sales_frame().assign(quantity=[7, 7, 7, 7])))
    bundle = DatasetBundle("retail", "1", {"sales": make_sales()}, SOURCE)
    with pytest.raises(DatasetAlreadyRegisteredError, match="different content"):
        catalog.register_bundle(bundle)
    with pytest.raises(DatasetNotFoundError):
        catalog.get_bundle("retail")


def test_from_settings_uses_data_dir(tmp_path: Path) -> None:
    settings = load_settings(
        data_dir=tmp_path / "data", database_url=f"sqlite:///{tmp_path / 'data' / 'c.sqlite'}"
    )
    catalog = DatasetCatalog.from_settings(settings)
    assert catalog.artifact_root == tmp_path / "data" / "processed" / "artifacts"


def test_registered_dataset_reloads_identically_in_a_new_process(tmp_path: Path) -> None:
    """Gate 2: register → reload in a new process → identical content hash."""
    catalog = DatasetCatalog(f"sqlite:///{tmp_path / 'c.sqlite'}", tmp_path / "artifacts")
    expected = catalog.register(make_sales()).content_hash
    script = textwrap.dedent(
        """
        import sys
        from pathlib import Path
        from industrial_ai.foundation.catalog import DatasetCatalog
        catalog = DatasetCatalog(sys.argv[1], Path(sys.argv[2]))
        print(catalog.get("sales").metadata.content_hash)
        """
    )
    database_url = f"sqlite:///{tmp_path / 'c.sqlite'}"
    output = subprocess.run(
        [sys.executable, "-c", script, database_url, str(tmp_path / "artifacts")],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert output == expected
