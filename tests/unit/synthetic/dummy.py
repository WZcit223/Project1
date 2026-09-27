"""A minimal generator used to test the engine and registry contracts."""

import numpy as np
import pandas as pd
from pydantic import BaseModel

from industrial_ai.foundation.datasets import (
    Dataset,
    DatasetBundle,
    DatasetSchema,
    DType,
    FieldSpec,
)
from industrial_ai.foundation.provenance import TransformationStep
from industrial_ai.foundation.validation import ConstraintSet
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.synthetic import GeneratedData, GenerationSize

SCHEMA = DatasetSchema(
    schema_id="test.values",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="row_id", dtype=DType.INT),
        FieldSpec(name="value", dtype=DType.FLOAT, min=0),
    ),
    primary_key=("row_id",),
)


class DummyParams(BaseModel):
    scale: float = 1.0
    negative: bool = False


class DummyGenerator:
    generator_id = "dummy"
    generator_version = "1.0.0"
    description = "Uniform random values times a scale (tests only)."
    parameter_model: type[BaseModel] = DummyParams
    scenario_parameters: frozenset[str] = frozenset({"scale_multiplier"})

    def generate(
        self,
        schema: DatasetSchema,
        constraints: ConstraintSet,
        scenario: ScenarioSpec | None,
        seed: int,
        size: GenerationSize,
        parameters: BaseModel,
        reference: Dataset | DatasetBundle | None = None,
    ) -> GeneratedData:
        assert isinstance(parameters, DummyParams)
        rows = size.rows if size.rows is not None else 10
        multiplier = 1.0
        if scenario is not None:
            raw = scenario.parameters.get("scale_multiplier", 1.0)
            assert isinstance(raw, int | float)
            multiplier = float(raw)
        values = np.random.default_rng(seed).uniform(0, 1, rows) * parameters.scale * multiplier
        if parameters.negative:
            values = -values
        return GeneratedData(
            data=pd.DataFrame({"row_id": np.arange(rows, dtype="int64"), "value": values}),
            transformations=(TransformationStep(step="sample_uniform", details={"rows": rows}),),
        )
