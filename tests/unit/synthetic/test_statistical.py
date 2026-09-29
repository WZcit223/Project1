"""Tests for the statistical generator (TASK-SYN-004)."""

from collections.abc import Mapping

import numpy as np
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
    SyntheticDataset,
    SyntheticEngine,
    new_generator_registry,
)
from industrial_ai.synthetic.generators import StatisticalGenerator

SCHEMA = DatasetSchema(
    schema_id="test.lead_times",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="lead_mean", dtype=DType.FLOAT),
        FieldSpec(name="lead_std", dtype=DType.FLOAT),
        FieldSpec(name="orders", dtype=DType.INT, min=0),
        FieldSpec(name="tier", dtype=DType.STR),
    ),
)
COLUMNS: dict[str, object] = {
    "lead_mean": {"kind": "gamma", "shape": 9.0, "scale": 0.5},
    "lead_std": {"kind": "lognormal", "mean": 0.0, "sigma": 0.25, "decimals": 3},
    "orders": {"kind": "negative_binomial", "mean": 4.0, "dispersion": 2.0, "integer": True},
    "tier": {"kind": "categorical", "values": ["A", "B", "C"], "weights": [0.5, 0.3, 0.2]},
}
ROWS = 20_000


def generate(
    parameters: Mapping[str, object] | None = None, seed: int = 7, rows: int = ROWS
) -> SyntheticDataset:
    registry = new_generator_registry()
    registry.register(StatisticalGenerator())
    request = GenerationRequest(
        generator_id="statistical",
        dataset_id="lead_times",
        output_schema=SCHEMA,
        seed=seed,
        size=GenerationSize(rows=rows),
        parameters=parameters or {"columns": COLUMNS},  # type: ignore[arg-type]
    )
    return SyntheticEngine(registry).generate(request)


def test_is_a_generator() -> None:
    assert isinstance(StatisticalGenerator(), SyntheticDataGenerator)


def test_marginals_match_their_distributions() -> None:
    data = generate().data
    assert data["lead_mean"].mean() == pytest.approx(4.5, rel=0.03)  # gamma: shape * scale
    assert data["orders"].mean() == pytest.approx(4.0, rel=0.03)
    assert data["orders"].var() == pytest.approx(4.0 + 16.0 / 2.0, rel=0.08)  # mu + mu^2/k
    assert str(data["orders"].dtype) == "int64"
    assert data["tier"].value_counts(normalize=True)["A"] == pytest.approx(0.5, abs=0.02)
    assert (data["lead_std"].round(3) == data["lead_std"]).all()


def spearman(a: pd.Series, b: pd.Series) -> float:
    return float(a.rank().corr(b.rank()))


def test_rank_correlation_is_imposed_and_marginals_kept() -> None:
    params = {
        "columns": COLUMNS,
        "correlation": {"columns": ["lead_mean", "lead_std"], "matrix": [[1, 0.8], [0.8, 1]]},
    }
    correlated = generate(params).data
    independent = generate().data
    assert spearman(correlated["lead_mean"], correlated["lead_std"]) == pytest.approx(0.8, abs=0.05)
    assert abs(spearman(independent["lead_mean"], independent["lead_std"])) < 0.05
    assert np.allclose(np.sort(correlated["lead_mean"]), np.sort(independent["lead_mean"]))


def test_clipping_is_explicit_and_recorded() -> None:
    columns = COLUMNS | {"lead_mean": {"kind": "normal", "mean": 1.0, "std": 2.0, "clip_min": 0.5}}
    result = generate({"columns": columns}, rows=2000)
    assert result.data["lead_mean"].min() == 0.5
    clip = [t for t in result.provenance.transformations if t.step == "clip"]
    counts = clip[0].details["clipped_values"]
    assert (
        isinstance(counts, dict)
        and isinstance(counts["lead_mean"], int)
        and counts["lead_mean"] > 0
    )


def test_reproducible_and_seed_sensitive() -> None:
    a, b, c = generate(seed=1, rows=500), generate(seed=1, rows=500), generate(seed=2, rows=500)
    assert a.metadata.content_hash == b.metadata.content_hash != c.metadata.content_hash


def test_copy_from_reference_gives_one_row_per_reference_row() -> None:
    reference = build_dataset(
        dataset_id="suppliers",
        version="1",
        schema=DatasetSchema(
            schema_id="test.supplier",
            schema_version="1.0.0",
            fields=(FieldSpec(name="supplier_id", dtype=DType.STR),),
        ),
        data=pd.DataFrame({"supplier_id": ["S1", "S2", "S3"]}),
        source=SourceInfo(name="suppliers", source_type=SourceType.FIXTURE),
        lineage=Lineage(),
    )
    schema = DatasetSchema(
        schema_id="test.supplier_lead",
        schema_version="1.0.0",
        fields=(
            FieldSpec(name="supplier_id", dtype=DType.STR),
            FieldSpec(name="lead_mean", dtype=DType.FLOAT),
        ),
    )
    registry = new_generator_registry()
    registry.register(StatisticalGenerator())
    request = GenerationRequest(
        generator_id="statistical",
        dataset_id="supplier_lead",
        output_schema=schema,
        seed=3,
        parameters={
            "copy_from_reference": ["supplier_id"],
            "columns": {"lead_mean": {"kind": "uniform", "low": 2, "high": 9}},
        },
    )
    result = SyntheticEngine(registry).generate(request, reference=reference)
    assert result.data["supplier_id"].tolist() == ["S1", "S2", "S3"]


@pytest.mark.parametrize(
    "params",
    [
        {
            "columns": COLUMNS,
            "correlation": {"columns": ["lead_mean", "lead_std"], "matrix": [[1, 2], [2, 1]]},
        },
        {
            "columns": COLUMNS,
            "correlation": {"columns": ["lead_mean", "tier"], "matrix": [[1, 0], [0, 1]]},
        },
        {"columns": COLUMNS | {"orders": {"kind": "uniform", "low": 5, "high": 1}}},
        {"columns": {"lead_mean": COLUMNS["lead_mean"]}},
    ],
    ids=["bad-matrix", "categorical-correlated", "bad-uniform", "missing-columns"],
)
def test_invalid_parameters(params: dict[str, object]) -> None:
    with pytest.raises(GeneratorParameterError):
        generate(params, rows=10)
