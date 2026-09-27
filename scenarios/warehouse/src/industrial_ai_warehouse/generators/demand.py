"""Scenario-specific synthetic demand (``ops.synthetic_demand``) via the time_series generator.

Warehouse scenario parameters are mapped onto the generator's generic effects:
``demand_multiplier → level_multiplier``; ``seasonality_multiplier``, ``noise_scale`` and the shock
parameters keep their names. Supply-side parameters (lead time, capacity) are not demand effects:
the engine reports them as not applied by this generator, and the inventory simulation uses them.
"""

from datetime import date, datetime

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from industrial_ai.foundation.datasets import Dataset, DatasetBundle
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.synthetic import (
    GenerationRequest,
    GenerationSize,
    SyntheticDataset,
    SyntheticEngine,
)
from industrial_ai.synthetic.generators import builtin_registry
from industrial_ai_warehouse.generators._support import derived_dataset, table_seed
from industrial_ai_warehouse.schemas.operations import DEMAND_TIMELINE, SYNTHETIC_DEMAND

SCENARIO_MAPPING: dict[str, JsonValue] = {"level_multiplier": "demand_multiplier"}


class DemandConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    start: date
    periods: int = Field(default=182, ge=1)
    history_window_days: int = Field(default=730, ge=28)
    distribution: str = "negative_binomial"


def generate_synthetic_demand(
    retail: DatasetBundle,
    config: DemandConfig,
    seed: int,
    scenario: ScenarioSpec | None = None,
    engine: SyntheticEngine | None = None,
    created_at: datetime | None = None,
) -> SyntheticDataset:
    """Calibrate on ``retail.sales``; generate daily demand for the horizon under ``scenario``."""
    engine = engine or SyntheticEngine(builtin_registry())
    scenario_id = scenario.scenario_id if scenario else "none"
    return engine.generate(
        GenerationRequest(
            generator_id="time_series",
            dataset_id=f"{retail.bundle_id}.demand.{scenario_id}.s{seed}",
            output_schema=SYNTHETIC_DEMAND,
            scenario=scenario,
            # Same random stream for every scenario (common random numbers): differences between
            # scenarios then come from the scenario parameters, not from sampling noise.
            seed=table_seed(seed, "demand"),
            size=GenerationSize(start=config.start, periods=config.periods),
            parameters={
                "entity_columns": ["product_id", "store_id"],
                "distribution": config.distribution,
                "history_window_days": config.history_window_days,
                "reference_table": "sales",
                "scenario_mapping": SCENARIO_MAPPING,
                "scenario_id_column": "scenario_id",
            },
            tags=("synthetic", "warehouse", "demand"),
        ),
        reference=retail,
        created_at=created_at,
    )


def build_demand_timeline(
    retail: DatasetBundle, demand: Dataset, created_at: datetime | None = None
) -> Dataset:
    """``derived.demand_timeline``: observed sales, then the synthetic horizon demand.

    Input for rolling forecasts during a simulation: a forecast at origin ``o`` sees observed
    history and the synthetic demand of horizon days before ``o`` (never later days). Only the
    (product, store) series present in ``demand`` are kept.
    """
    sales = retail.table("sales")
    columns = ["date", "product_id", "store_id", "quantity"]
    observed = sales.data[columns].copy()
    synthetic = demand.data[columns].copy()
    first_synthetic = pd.to_datetime(synthetic["date"]).min()
    if pd.to_datetime(observed["date"]).max() >= first_synthetic:
        raise ValueError(
            f"synthetic demand starts {first_synthetic.date()}, inside the observed history"
        )
    series = synthetic[["product_id", "store_id"]].drop_duplicates()
    observed = observed.merge(series, on=["product_id", "store_id"], how="inner")
    frame = pd.concat(
        [observed.assign(origin="observed"), synthetic.assign(origin="synthetic")],
        ignore_index=True,
    ).sort_values(["date", "product_id", "store_id"], kind="stable")
    return derived_dataset(
        dataset_id=f"{demand.dataset_id}.timeline",
        schema=DEMAND_TIMELINE,
        frame=frame.reset_index(drop=True),
        inputs=(sales, demand),
        step="concat_observed_and_synthetic",
        details={"observed_rows": len(observed), "synthetic_rows": len(synthetic)},
        created_at=created_at,
    )
