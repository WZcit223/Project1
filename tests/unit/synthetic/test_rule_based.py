"""Tests for the rule_based generator (TASK-SYN-003)."""

import pandas as pd
import pytest

from industrial_ai.core.errors import GeneratorParameterError
from industrial_ai.foundation.datasets import (
    DatasetSchema,
    DType,
    FieldSpec,
    SourceInfo,
    SourceType,
    build_dataset,
)
from industrial_ai.foundation.provenance import Lineage
from industrial_ai.synthetic import (
    GenerationRequest,
    GenerationSize,
    SyntheticDataGenerator,
    SyntheticEngine,
    new_generator_registry,
)
from industrial_ai.synthetic.generators import RuleBasedGenerator

SUPPLIER = DatasetSchema(
    schema_id="test.supplier",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="supplier_id", dtype=DType.STR),
        FieldSpec(name="tier", dtype=DType.STR, allowed_values=("A", "B")),
        FieldSpec(name="capacity", dtype=DType.INT, min=10, max=20),
        FieldSpec(name="order_cost", dtype=DType.FLOAT),
        FieldSpec(name="rush_cost", dtype=DType.FLOAT),
        FieldSpec(name="tier_label", dtype=DType.STR),
    ),
    primary_key=("supplier_id",),
)
RULES = {
    "supplier_id": {"kind": "sequence", "prefix": "SUP", "width": 3},
    "tier": {"kind": "choice", "values": ["A", "B"], "weights": [0.8, 0.2]},
    "capacity": {"kind": "uniform", "low": 10, "high": 20, "integer": True},
    "order_cost": {"kind": "constant", "value": 25.0},
    "rush_cost": {"kind": "linear", "source": "order_cost", "scale": 1.5, "offset": 2},
    "tier_label": {
        "kind": "lookup",
        "source": "tier",
        "mapping": {"A": "preferred"},
        "default": "standard",
    },
}


def engine() -> SyntheticEngine:
    registry = new_generator_registry()
    registry.register(RuleBasedGenerator())
    return SyntheticEngine(registry)


def generate(seed: int = 1, **overrides: object) -> pd.DataFrame:
    base: dict[str, object] = {
        "generator_id": "rule_based",
        "dataset_id": "suppliers",
        "output_schema": SUPPLIER,
        "seed": seed,
        "size": GenerationSize(rows=50),
        "parameters": {"columns": RULES},
    }
    return engine().generate(GenerationRequest.model_validate(base | overrides)).data


def test_is_a_generator() -> None:
    assert isinstance(RuleBasedGenerator(), SyntheticDataGenerator)


def test_rules_produce_valid_table() -> None:
    frame = generate()
    assert list(frame["supplier_id"][:3]) == ["SUP001", "SUP002", "SUP003"]
    assert set(frame["tier"]) <= {"A", "B"}
    assert frame["capacity"].between(10, 20).all()
    assert (frame["rush_cost"] == 39.5).all()
    assert (frame.loc[frame["tier"] == "A", "tier_label"] == "preferred").all()
    assert (frame.loc[frame["tier"] == "B", "tier_label"] == "standard").all()


def test_reproducible_and_seed_sensitive() -> None:
    assert generate(1).equals(generate(1))
    assert not generate(1).equals(generate(2))


def test_one_row_per_reference_row() -> None:
    products = build_dataset(
        dataset_id="products",
        version="1",
        schema=DatasetSchema(
            schema_id="test.product",
            schema_version="1.0.0",
            fields=(
                FieldSpec(name="product_id", dtype=DType.STR),
                FieldSpec(name="price", dtype=DType.FLOAT),
            ),
        ),
        data=pd.DataFrame({"product_id": ["P1", "P2", "P3"], "price": [2.0, 4.0, 10.0]}),
        source=SourceInfo(name="products", source_type=SourceType.FIXTURE),
        lineage=Lineage(),
    )
    schema = DatasetSchema(
        schema_id="test.product_cost",
        schema_version="1.0.0",
        fields=(
            FieldSpec(name="product_id", dtype=DType.STR),
            FieldSpec(name="unit_cost", dtype=DType.FLOAT),
        ),
    )
    request = GenerationRequest(
        generator_id="rule_based",
        dataset_id="costs",
        output_schema=schema,
        seed=0,
        parameters={
            "columns": {
                "product_id": {"kind": "reference_column", "column": "product_id"},
                "unit_cost": {"kind": "linear", "source": "price", "scale": 0.7, "decimals": 2},
            }
        },
    )
    result = engine().generate(request, reference=products)
    assert result.data["unit_cost"].tolist() == [1.4, 2.8, 7.0]
    assert result.provenance.inputs[0].dataset_id == "products"


@pytest.mark.parametrize(
    ("columns", "message"),
    [
        ({k: v for k, v in RULES.items() if k != "tier"}, "missing"),
        (RULES | {"rush_cost": {"kind": "linear", "source": "nope"}}, "unknown source"),
    ],
)
def test_invalid_configuration(columns: dict[str, object], message: str) -> None:
    with pytest.raises(GeneratorParameterError, match=message):
        generate(parameters={"columns": columns})


def test_rows_needed_without_reference() -> None:
    with pytest.raises(GeneratorParameterError, match=r"size\.rows"):
        generate(size=GenerationSize())


def test_bad_choice_weights_rejected() -> None:
    with pytest.raises(GeneratorParameterError):
        generate(
            parameters={
                "columns": RULES | {"tier": {"kind": "choice", "values": ["A"], "weights": [1, 2]}}
            }
        )
