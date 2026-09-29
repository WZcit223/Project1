"""Gate 4: synthetic data is generated reproducibly, with provenance, from catalogued data.

Fixture (M5 layout) → M5 adapter → catalog → rule_based / statistical / time_series via the engine
→ registered synthetic datasets; a second, independent run yields identical content hashes.
"""

from datetime import date
from pathlib import Path

from industrial_ai.foundation.catalog import DatasetCatalog
from industrial_ai.foundation.datasets import DatasetSchema, DType, FieldSpec, SourceType
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.synthetic import (
    GenerationRequest,
    GenerationSize,
    SyntheticEngine,
    new_generator_registry,
)
from industrial_ai.synthetic.generators import (
    RuleBasedGenerator,
    StatisticalGenerator,
    TimeSeriesGenerator,
)
from industrial_ai_warehouse.adapters.m5 import M5Adapter

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "m5_like"

DEMAND = DatasetSchema(
    schema_id="it.synthetic_demand",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="date", dtype=DType.DATE),
        FieldSpec(name="product_id", dtype=DType.STR),
        FieldSpec(name="store_id", dtype=DType.STR),
        FieldSpec(name="quantity", dtype=DType.INT, min=0),
        FieldSpec(name="scenario_id", dtype=DType.STR),
    ),
    primary_key=("date", "product_id", "store_id"),
    time_index="date",
)
PRODUCT_OPS = DatasetSchema(
    schema_id="it.product_ops",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="product_id", dtype=DType.STR),
        FieldSpec(name="supplier_id", dtype=DType.STR),
        FieldSpec(name="lead_time_mean_days", dtype=DType.FLOAT, min=1),
    ),
    primary_key=("product_id",),
)
HIGH_DEMAND = ScenarioSpec(
    scenario_id="high_demand",
    version="1.0.0",
    pack="warehouse",
    title="High demand",
    parameters={"demand_multiplier": 1.3, "seasonality_multiplier": 1.2, "lead_time_delta": 0},
)


def run(tmp: Path) -> dict[str, str]:
    catalog = DatasetCatalog(f"sqlite:///{tmp / 'catalog.sqlite'}", tmp / "artifacts")
    catalog.register_bundle(M5Adapter().load(FIXTURE))
    registry = new_generator_registry()
    for generator in (RuleBasedGenerator(), StatisticalGenerator(), TimeSeriesGenerator()):
        registry.register(generator)
    engine = SyntheticEngine(registry, catalog)

    demand = engine.generate(
        GenerationRequest(
            generator_id="time_series",
            dataset_id="syn_demand_high",
            output_schema=DEMAND,
            scenario=HIGH_DEMAND,
            seed=20260927,
            size=GenerationSize(start=date(2014, 2, 1), periods=91),
            parameters={
                "entity_columns": ["product_id", "store_id"],
                "scenario_id_column": "scenario_id",
                "scenario_mapping": {"level_multiplier": "demand_multiplier"},
            },
            reference_dataset_id="m5_fixture.sales",
        ),
        register=True,
    )
    ids = engine.generate(
        GenerationRequest(
            generator_id="rule_based",
            dataset_id="product_supplier_ids",
            output_schema=PRODUCT_OPS.model_copy(
                update={"fields": PRODUCT_OPS.fields[:2], "schema_id": "it.product_supplier"}
            ),
            seed=1,
            parameters={
                "columns": {
                    "product_id": {"kind": "reference_column", "column": "product_id"},
                    "supplier_id": {"kind": "choice", "values": ["SUP001", "SUP002"]},
                }
            },
            reference_dataset_id="m5_fixture.product",
        ),
        register=True,
    )
    ops = engine.generate(
        GenerationRequest(
            generator_id="statistical",
            dataset_id="product_ops",
            output_schema=PRODUCT_OPS,
            seed=2,
            parameters={
                "copy_from_reference": ["product_id", "supplier_id"],
                "columns": {
                    "lead_time_mean_days": {
                        "kind": "gamma",
                        "shape": 9,
                        "scale": 0.5,
                        "clip_min": 1,
                    }
                },
            },
            reference_dataset_id="product_supplier_ids",
        ),
        register=True,
    )
    assert demand.warnings and "lead_time_delta" in demand.warnings[0]
    assert ops.provenance.inputs[0].content_hash == ids.metadata.content_hash
    return {s.dataset_id: s.content_hash for s in catalog.list(SourceType.SYNTHETIC)}


def test_synthetic_generation_is_reproducible_end_to_end(tmp_path: Path) -> None:
    first = run(tmp_path / "run1")
    second = run(tmp_path / "run2")
    assert set(first) == {"syn_demand_high", "product_supplier_ids", "product_ops"}
    assert first == second
