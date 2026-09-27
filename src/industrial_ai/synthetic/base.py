"""Synthetic data generator protocol and data types (docs/synthetic-data-api.md §1–2).

Generators return :class:`GeneratedData` (a DataFrame plus the transformation steps they applied).
The :class:`~industrial_ai.synthetic.engine.SyntheticEngine` turns that into a
:class:`SyntheticDataset`: it computes hashes, writes provenance and validates constraints, so a
generator cannot produce data with missing or fabricated provenance.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol, Self, runtime_checkable

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from industrial_ai.foundation.datasets import Dataset, DatasetBundle, DatasetSchema
from industrial_ai.foundation.provenance import TransformationStep
from industrial_ai.foundation.validation import ConstraintSet, ValidationReport
from industrial_ai.scenario import ScenarioSpec


class GenerationSize(BaseModel):
    """How much to generate: ``rows`` for tables; ``start`` + ``periods`` (days) for time series.

    Fields left as ``None`` are derived by the generator (e.g. one row per reference row).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: int | None = Field(default=None, ge=0)
    start: date | None = None
    periods: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _start_with_periods(self) -> Self:
        if (self.start is None) != (self.periods is None):
            raise ValueError("start and periods must be given together")
        return self


@dataclass(frozen=True)
class GeneratedData:
    """Raw output of a generator, before the engine wraps it into a dataset."""

    data: pd.DataFrame
    transformations: tuple[TransformationStep, ...] = ()
    warnings: tuple[str, ...] = ()
    applied_scenario_parameters: frozenset[str] = frozenset()
    """Scenario parameter names actually applied; the engine warns about all others."""


@runtime_checkable
class SyntheticDataGenerator(Protocol):
    """A pluggable generator, registered by ``(generator_id, generator_version)``."""

    generator_id: str
    generator_version: str
    description: str
    parameter_model: type[BaseModel]
    scenario_parameters: frozenset[str]
    """Scenario effects this generator supports (for documentation and UIs). What was actually
    applied in a run is reported in :attr:`GeneratedData.applied_scenario_parameters`."""

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
        """Generate data conforming to ``schema``.

        ``parameters`` is an instance of ``parameter_model`` (validated by the engine). All
        randomness must come from ``seed``. Raise ``GeneratorParameterError`` for unusable inputs.
        """
        ...


class GenerationConfig(BaseModel):
    """Everything needed to repeat a generation run (together with the reference data)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    generator_id: str
    generator_version: str
    schema_id: str
    schema_version: str
    constraints: ConstraintSet
    scenario: ScenarioSpec | None
    seed: int
    size: GenerationSize
    parameters: dict[str, JsonValue]


@dataclass(frozen=True)
class SyntheticDataset(Dataset):
    """A generated :class:`Dataset` with its generation config and validation report."""

    generation_config: GenerationConfig
    validation_report: ValidationReport
    warnings: tuple[str, ...] = ()

    @property
    def generator_id(self) -> str:
        return self.generation_config.generator_id

    @property
    def generator_version(self) -> str:
        return self.generation_config.generator_version

    @property
    def random_seed(self) -> int:
        return self.generation_config.seed


class GeneratorInfo(BaseModel):
    """Public description of a registered generator (for APIs and UIs)."""

    model_config = ConfigDict(frozen=True)

    generator_id: str
    generator_version: str
    description: str
    parameter_schema: dict[str, Any]
    scenario_parameters: tuple[str, ...]
