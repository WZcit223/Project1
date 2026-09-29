"""derived.demand_timeline: observed history followed by synthetic horizon demand."""

from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from industrial_ai.foundation.validation import validate_dataset
from industrial_ai_warehouse.adapters.m5 import M5Adapter
from industrial_ai_warehouse.generators import (
    DemandConfig,
    build_demand_timeline,
    generate_synthetic_demand,
)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "m5_like"


def test_timeline_concatenates_history_and_horizon() -> None:
    retail = M5Adapter().load(FIXTURE)
    sales = retail.table("sales").data
    start = sales["date"].max().date() + timedelta(days=1)
    demand = generate_synthetic_demand(retail, DemandConfig(start=start, periods=14), seed=1)
    timeline = build_demand_timeline(retail, demand)

    frame = timeline.data
    assert validate_dataset(timeline).passed
    assert len(frame) == len(sales) + len(demand.data)
    observed = frame[frame["origin"] == "observed"]
    synthetic = frame[frame["origin"] == "synthetic"]
    assert pd.to_datetime(observed["date"]).max() < pd.Timestamp(start)
    assert synthetic["quantity"].sum() == demand.data["quantity"].sum()
    assert [i.dataset_id for i in timeline.provenance.inputs] == [
        retail.table("sales").dataset_id,
        demand.dataset_id,
    ]
    again = build_demand_timeline(retail, demand)
    assert again.metadata.content_hash == timeline.metadata.content_hash


def test_timeline_rejects_overlapping_horizon() -> None:
    retail = M5Adapter().load(FIXTURE)
    last = retail.table("sales").data["date"].max().date()
    demand = generate_synthetic_demand(retail, DemandConfig(start=last, periods=7), seed=1)
    with pytest.raises(ValueError, match="inside the observed history"):
        build_demand_timeline(retail, demand)
