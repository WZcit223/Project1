"""Rule-based generator ``rule_based`` 1.0.0 (docs/synthetic-data-api.md §6.1).

Builds a table column by column from a small, whitelisted rule vocabulary — no code or
expressions are evaluated. Rules may use columns defined earlier in the same table, and columns of
a reference table (one output row per reference row).

Example (supplier master)::

    {"columns": {
        "supplier_id": {"kind": "sequence", "prefix": "SUP", "width": 3},
        "region":      {"kind": "choice", "values": ["north", "south"], "weights": [0.7, 0.3]},
        "order_cost":  {"kind": "constant", "value": 25.0}}}
"""

from typing import Annotated, Literal, Self

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from industrial_ai.core.errors import GeneratorParameterError
from industrial_ai.foundation.datasets import Dataset, DatasetBundle, DatasetSchema
from industrial_ai.foundation.provenance import TransformationStep
from industrial_ai.foundation.validation import ConstraintSet
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.synthetic.base import GeneratedData, GenerationSize
from industrial_ai.synthetic.generators._common import check_columns, ordered, reference_table


class _Rule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ConstantRule(_Rule):
    kind: Literal["constant"] = "constant"
    value: JsonValue


class SequenceRule(_Rule):
    """Identifiers ``<prefix><n zero-padded to width>``, or plain integers if ``as_int``."""

    kind: Literal["sequence"] = "sequence"
    prefix: str = ""
    start: int = 1
    width: int = Field(default=3, ge=1)
    as_int: bool = False


class ChoiceRule(_Rule):
    kind: Literal["choice"] = "choice"
    values: tuple[JsonValue, ...] = Field(min_length=1)
    weights: tuple[float, ...] | None = None

    @model_validator(mode="after")
    def _weights(self) -> Self:
        if self.weights is not None and (
            len(self.weights) != len(self.values) or min(self.weights) < 0 or sum(self.weights) <= 0
        ):
            raise ValueError("weights must be non-negative, one per value, and not all zero")
        return self


class UniformRule(_Rule):
    kind: Literal["uniform"] = "uniform"
    low: float
    high: float
    integer: bool = False
    decimals: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _bounds(self) -> Self:
        if self.low > self.high:
            raise ValueError("low must be <= high")
        return self


class LinearRule(_Rule):
    """``source * scale + offset`` (source = an earlier column or a reference column)."""

    kind: Literal["linear"] = "linear"
    source: str
    scale: float = 1.0
    offset: float = 0.0
    decimals: int | None = Field(default=None, ge=0)
    integer: bool = False


class LookupRule(_Rule):
    """Map values of ``source`` through ``mapping``; unmapped values take ``default``."""

    kind: Literal["lookup"] = "lookup"
    source: str
    mapping: dict[str, JsonValue]
    default: JsonValue = None


class ReferenceColumnRule(_Rule):
    """Copy a column of the reference table (one output row per reference row)."""

    kind: Literal["reference_column"] = "reference_column"
    column: str


Rule = Annotated[
    ConstantRule
    | SequenceRule
    | ChoiceRule
    | UniformRule
    | LinearRule
    | LookupRule
    | ReferenceColumnRule,
    Field(discriminator="kind"),
]


class RuleBasedParameters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    columns: dict[str, Rule] = Field(min_length=1)
    """Output column → rule, evaluated in the given order."""
    reference_table: str | None = None
    """Table name when the reference is a bundle."""


class RuleBasedGenerator:
    generator_id = "rule_based"
    generator_version = "1.0.0"
    description = "Tables from explicit rules: constants, id sequences, choices, ranges, lookups."
    parameter_model: type[BaseModel] = RuleBasedParameters
    scenario_parameters: frozenset[str] = frozenset()

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
        if not isinstance(parameters, RuleBasedParameters):
            raise GeneratorParameterError("rule_based expects RuleBasedParameters")
        check_columns(list(parameters.columns), schema, self.generator_id)
        ref = reference_table(reference, parameters.reference_table, self.generator_id)
        rows = _row_count(size, ref)
        rng = np.random.default_rng(seed)
        frame = pd.DataFrame(index=pd.RangeIndex(rows))
        for name, rule in parameters.columns.items():
            frame[name] = _apply(name, rule, rows, rng, frame, ref)
        step = TransformationStep(
            step="apply_rules",
            details={
                "rows": rows,
                "rules": {name: rule.kind for name, rule in parameters.columns.items()},
                "reference_rows": len(ref.data) if ref is not None else None,
            },
        )
        return GeneratedData(data=ordered(frame, schema), transformations=(step,))


def _row_count(size: GenerationSize, ref: Dataset | None) -> int:
    if size.rows is not None:
        if ref is not None and size.rows != len(ref.data):
            raise GeneratorParameterError(
                f"rule_based: size.rows={size.rows} but the reference has {len(ref.data)} rows"
            )
        return size.rows
    if ref is not None:
        return len(ref.data)
    raise GeneratorParameterError("rule_based: set size.rows or provide a reference table")


def _source(name: str, source: str, frame: pd.DataFrame, ref: Dataset | None) -> pd.Series:
    if source in frame.columns:
        return frame[source]
    if ref is not None and source in ref.data.columns:
        return ref.data[source].reset_index(drop=True)
    raise GeneratorParameterError(
        f"rule_based: column {name!r} uses unknown source {source!r} "
        "(must be an earlier column or a reference column)"
    )


def _numeric(values: pd.Series | np.ndarray, integer: bool, decimals: int | None) -> pd.Series:
    series = pd.Series(values, dtype="float64")
    if integer:
        return series.round().astype("int64")
    return series.round(decimals) if decimals is not None else series


def _apply(
    name: str,
    rule: Rule,
    rows: int,
    rng: np.random.Generator,
    frame: pd.DataFrame,
    ref: Dataset | None,
) -> pd.Series:
    match rule:
        case ConstantRule(value=value):
            return pd.Series([value] * rows)
        case SequenceRule(prefix=prefix, start=start, width=width, as_int=as_int):
            numbers = range(start, start + rows)
            if as_int:
                return pd.Series(list(numbers), dtype="int64")
            return pd.Series([f"{prefix}{n:0{width}d}" for n in numbers])
        case ChoiceRule(values=values, weights=weights):
            p = None if weights is None else np.asarray(weights) / sum(weights)
            index = rng.choice(len(values), size=rows, p=p)
            return pd.Series([values[i] for i in index])
        case UniformRule(low=low, high=high, integer=integer, decimals=decimals):
            if integer:
                return pd.Series(rng.integers(int(low), int(high), endpoint=True, size=rows))
            return _numeric(rng.uniform(low, high, size=rows), False, decimals)
        case LinearRule(source=source, scale=scale, offset=offset, decimals=d, integer=integer):
            base = pd.to_numeric(_source(name, source, frame, ref))
            return _numeric(base * scale + offset, integer, d)
        case LookupRule(source=source, mapping=mapping, default=default):
            keys = _source(name, source, frame, ref).astype("object").map(str)
            return keys.map(lambda k: mapping.get(k, default))
        case ReferenceColumnRule(column=column):
            if ref is None or column not in ref.data.columns:
                raise GeneratorParameterError(
                    f"rule_based: column {name!r} copies unknown reference column {column!r}"
                )
            return ref.data[column].reset_index(drop=True)
    raise GeneratorParameterError(f"rule_based: unsupported rule {rule!r}")  # pragma: no cover
