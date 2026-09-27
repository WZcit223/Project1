"""Scenario-specific synthetic demand (``ops.synthetic_demand``) via the time_series generator.

Warehouse scenario parameters are mapped onto the generator's generic effects:
``demand_multiplier → level_multiplier``; ``seasonality_multiplier``, ``noise_scale`` and the shock
parameters keep their names. Supply-side parameters (lead time, capacity) are not demand effects:
the engine reports them as not applied by this generator, and the inventory simulation uses them.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from industrial_ai.foundation.datasets import DatasetBundle
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.synthetic import (
    GenerationRequest,
    GenerationSize,
    SyntheticDataset,
    SyntheticEngine,
)
from industrial_ai.synthetic.generators import builtin_registry
from industrial_ai_warehouse.generators._support import table_seed
from industrial_ai_warehouse.schemas.operations import SYNTHETIC_DEMAND

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
