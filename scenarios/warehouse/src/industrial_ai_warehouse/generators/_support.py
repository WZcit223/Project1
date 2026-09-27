"""Helpers shared by the warehouse generation configurations."""

import hashlib
from collections.abc import Sequence
from datetime import datetime

import pandas as pd
from pydantic import JsonValue

from industrial_ai.foundation.datasets import (
    Dataset,
    DatasetSchema,
    SourceInfo,
    SourceType,
    build_dataset,
)
from industrial_ai.foundation.provenance import ComponentRef, Lineage, TransformationStep

DERIVE_COMPONENT = ComponentRef(id="warehouse.derive", version="1.0.0")


def table_seed(seed: int, table: str) -> int:
    """Independent, reproducible seed per generated table."""
    digest = hashlib.sha256(f"{seed}:{table}".encode()).digest()
    return int.from_bytes(digest[:4], "big")


def derived_dataset(
    *,
    dataset_id: str,
    schema: DatasetSchema,
    frame: pd.DataFrame,
    inputs: Sequence[Dataset],
    step: str,
    details: dict[str, JsonValue],
    created_at: datetime | None,
) -> Dataset:
    """A deterministic summary of other datasets, with provenance pointing at them."""
    return build_dataset(
        dataset_id=dataset_id,
        version="1",
        schema=schema,
        data=frame,
        source=SourceInfo(
            name=dataset_id,
            description=schema.description,
            source_type=SourceType.DERIVED,
            tags=("warehouse", "derived"),
        ),
        lineage=Lineage(
            inputs=tuple(d.as_input() for d in inputs),
            component=DERIVE_COMPONENT,
            transformations=(TransformationStep(step=step, details=details),),
        ),
        created_at=created_at,
    )


def mean_daily_demand(sales: pd.DataFrame, window_days: int) -> pd.DataFrame:
    """Mean daily units per product and store over the last ``window_days`` of active history.

    Days before a series' first sale are excluded (not yet available ≠ zero demand).
    """
    end = sales["date"].max()
    window_start = end - pd.Timedelta(days=window_days - 1)
    rows = []
    for (product, store), series in sales.groupby(["product_id", "store_id"], sort=True):
        sold = series.loc[series["quantity"] > 0, "date"]
        if sold.empty:
            mean = 0.0
        else:
            active = series[series["date"] >= max(sold.min(), window_start)]
            mean = float(active["quantity"].mean())
        rows.append({"product_id": product, "store_id": store, "mean_daily_demand": round(mean, 6)})
    return pd.DataFrame(rows)
