"""Extract a small M5 subset from the full Kaggle files (run locally by the data owner).

Streams the large sales and price files in chunks, keeps the selected stores / departments /
categories and the top-N items by total sales, and writes files in the original M5 layout plus a
``SOURCE.json`` with the filters, original-file hashes and download date. Values are copied as
text, byte-for-byte, so the subset is exactly the original data for the selected series.
"""

import hashlib
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from industrial_ai.core.errors import IngestionError
from industrial_ai.foundation.datasets import SourceType
from industrial_ai_warehouse.adapters.m5.source import (
    CALENDAR_FILE,
    M5_NAME,
    PRICES_FILE,
    SALES_FILES,
    M5Source,
    SubsetFilters,
)

SUBSET_TOOL_VERSION = "1.0.0"
_HASH_BLOCK = 1 << 20


def make_subset(
    input_dir: Path,
    output_dir: Path,
    filters: SubsetFilters,
    *,
    download_date: date | None = None,
    dataset_id: str | None = None,
    chunksize: int = 2000,
) -> M5Source:
    """Write an M5-layout subset of ``input_dir`` into ``output_dir`` and return its SOURCE record.

    Raises:
        IngestionError: missing input files, or no series match the filters.
    """
    sales_path = next((input_dir / n for n in SALES_FILES if (input_dir / n).is_file()), None)
    if sales_path is None:
        raise IngestionError(
            f"{input_dir}: missing sales file (expected one of {list(SALES_FILES)})"
        )
    for name in (CALENDAR_FILE, PRICES_FILE):
        if not (input_dir / name).is_file():
            raise IngestionError(f"{input_dir}: missing {name}")

    sales = _select_sales(sales_path, filters, chunksize)
    series = set(zip(sales["item_id"], sales["store_id"], strict=True))
    prices = _select_prices(input_dir / PRICES_FILE, series, chunksize)

    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(input_dir / CALENDAR_FILE, output_dir / CALENDAR_FILE)
    sales.to_csv(output_dir / sales_path.name, index=False, lineterminator="\n")
    prices.to_csv(output_dir / PRICES_FILE, index=False, lineterminator="\n")

    record = M5Source(
        dataset_id=dataset_id or default_dataset_id(filters),
        version="1",
        source_type=SourceType.REFERENCE,
        dataset_name=f"{M5_NAME} subset ({describe(filters)})",
        download_date=download_date,
        filters=filters,
        source_files={
            p.name: _sha256(p)
            for p in (input_dir / CALENDAR_FILE, input_dir / PRICES_FILE, sales_path)
        },
        created_at=datetime.now(UTC),
        created_by=f"industrial_ai_warehouse.adapters.m5.subset {SUBSET_TOOL_VERSION}",
        notes=(
            f"{len(sales)} series, {len(prices)} price rows. Real M5 data: keep out of Git and "
            "do not redistribute." + ("" if download_date else " Download date not provided.")
        ),
    )
    record.write(output_dir)
    return record


def default_dataset_id(filters: SubsetFilters) -> str:
    parts = [*filters.stores, *filters.departments, *filters.categories]
    suffix = f"_top{filters.top_n}" if filters.top_n else ""
    return ("m5_subset_" + "_".join(p.lower() for p in parts)).rstrip("_") + suffix


def describe(filters: SubsetFilters) -> str:
    parts = [
        f"stores={','.join(filters.stores) or 'all'}",
        f"departments={','.join(filters.departments) or 'all'}",
        f"categories={','.join(filters.categories) or 'all'}",
        f"top_n={filters.top_n or 'all'}",
    ]
    return "; ".join(parts)


def _select_sales(path: Path, filters: SubsetFilters, chunksize: int) -> pd.DataFrame:
    kept = []
    for chunk in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=chunksize):
        mask = pd.Series(True, index=chunk.index)
        if filters.stores:
            mask &= chunk["store_id"].isin(filters.stores)
        if filters.departments:
            mask &= chunk["dept_id"].isin(filters.departments)
        if filters.categories:
            mask &= chunk["cat_id"].isin(filters.categories)
        kept.append(chunk[mask])
    sales = pd.concat(kept, ignore_index=True)
    if sales.empty:
        raise IngestionError(f"no M5 series match the filters ({describe(filters)})")
    if filters.top_n is not None:
        days = [c for c in sales.columns if c.startswith("d_")]
        totals = sales[days].apply(pd.to_numeric).sum(axis=1).groupby(sales["item_id"]).sum()
        ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
        top = {item for item, _ in ranked[: filters.top_n]}
        sales = sales[sales["item_id"].isin(top)]
    return sales.reset_index(drop=True)


def _select_prices(path: Path, series: set[tuple[str, str]], chunksize: int) -> pd.DataFrame:
    kept = []
    for chunk in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=chunksize):
        pairs = zip(chunk["item_id"], chunk["store_id"], strict=True)
        kept.append(chunk[[pair in series for pair in pairs]])
    return pd.concat(kept, ignore_index=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(_HASH_BLOCK):
            digest.update(block)
    return "sha256:" + digest.hexdigest()
