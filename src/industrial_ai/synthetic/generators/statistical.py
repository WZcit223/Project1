"""Statistical generator ``statistical`` 1.0.0 (docs/synthetic-data-api.md §6.2).

Samples each column from a parametric distribution. Optional rank correlation between numeric
columns uses the Iman–Conover method: marginals are sampled independently, then reordered so their
ranks follow a correlated Gaussian sample. Marginal distributions are preserved exactly; the target
correlation is achieved approximately (as a rank correlation). Clipping and rounding are explicit
parameters and are recorded in provenance.
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


class _Numeric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    clip_min: float | None = None
    clip_max: float | None = None
    integer: bool = False
    decimals: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _clip_bounds(self) -> Self:
        if (
            self.clip_min is not None
            and self.clip_max is not None
            and self.clip_min > self.clip_max
        ):
            raise ValueError("clip_min must be <= clip_max")
        return self


class Normal(_Numeric):
    kind: Literal["normal"] = "normal"
    mean: float
    std: float = Field(ge=0)


class LogNormal(_Numeric):
    """``exp(N(mean, sigma))``: mean/sigma of the underlying normal."""

    kind: Literal["lognormal"] = "lognormal"
    mean: float
    sigma: float = Field(ge=0)


class Gamma(_Numeric):
    kind: Literal["gamma"] = "gamma"
    shape: float = Field(gt=0)
    scale: float = Field(gt=0)


class Poisson(_Numeric):
    kind: Literal["poisson"] = "poisson"
    lam: float = Field(ge=0)


class NegativeBinomial(_Numeric):
    """Counts with mean ``mean`` and variance ``mean + mean² / dispersion``."""

    kind: Literal["negative_binomial"] = "negative_binomial"
    mean: float = Field(gt=0)
    dispersion: float = Field(gt=0)


class Uniform(_Numeric):
    kind: Literal["uniform"] = "uniform"
    low: float
    high: float

    @model_validator(mode="after")
    def _bounds(self) -> Self:
        if self.low > self.high:
            raise ValueError("low must be <= high")
        return self


class Categorical(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["categorical"] = "categorical"
    values: tuple[JsonValue, ...] = Field(min_length=1)
    weights: tuple[float, ...] | None = None

    @model_validator(mode="after")
    def _weights(self) -> Self:
        if self.weights is not None and (
            len(self.weights) != len(self.values) or min(self.weights) < 0 or sum(self.weights) <= 0
        ):
            raise ValueError("weights must be non-negative, one per value, and not all zero")
        return self


Distribution = Annotated[
    Normal | LogNormal | Gamma | Poisson | NegativeBinomial | Uniform | Categorical,
    Field(discriminator="kind"),
]
NumericDistribution = Normal | LogNormal | Gamma | Poisson | NegativeBinomial | Uniform


class Correlation(BaseModel):
    """Target rank correlation between numeric columns.

    The matrix must be symmetric, with unit diagonal, and positive definite.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    columns: tuple[str, ...] = Field(min_length=2)
    matrix: tuple[tuple[float, ...], ...]

    @model_validator(mode="after")
    def _valid_matrix(self) -> Self:
        m = np.asarray(self.matrix, dtype=float)
        k = len(self.columns)
        if m.shape != (k, k):
            raise ValueError(f"matrix must be {k}x{k}")
        if not np.allclose(m, m.T) or not np.allclose(np.diag(m), 1.0) or np.abs(m).max() > 1:
            raise ValueError("matrix must be symmetric with unit diagonal and entries in [-1, 1]")
        try:
            np.linalg.cholesky(m)
        except np.linalg.LinAlgError:
            raise ValueError("matrix must be positive definite") from None
        return self


class StatisticalParameters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    columns: dict[str, Distribution] = Field(min_length=1)
    copy_from_reference: tuple[str, ...] = ()
    """Reference columns copied row-wise (e.g. ids); output has one row per reference row."""
    reference_table: str | None = None
    correlation: Correlation | None = None

    @model_validator(mode="after")
    def _correlated_columns_are_numeric(self) -> Self:
        if self.correlation is None:
            return self
        for name in self.correlation.columns:
            spec = self.columns.get(name)
            if spec is None or isinstance(spec, Categorical):
                raise ValueError(
                    f"correlated column {name!r} must be a numeric distribution column"
                )
        return self


class StatisticalGenerator:
    generator_id = "statistical"
    generator_version = "1.0.0"
    description = "Samples columns from parametric distributions, with optional rank correlation."
    parameter_model: type[BaseModel] = StatisticalParameters
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
        if not isinstance(parameters, StatisticalParameters):
            raise GeneratorParameterError("statistical expects StatisticalParameters")
        check_columns(
            [*parameters.copy_from_reference, *parameters.columns], schema, self.generator_id
        )
        ref = reference_table(reference, parameters.reference_table, self.generator_id)
        rows = _row_count(size, ref, parameters)
        rng = np.random.default_rng(seed)

        frame = pd.DataFrame(index=pd.RangeIndex(rows))
        for column in parameters.copy_from_reference:
            if ref is None or column not in ref.data.columns:
                raise GeneratorParameterError(f"statistical: unknown reference column {column!r}")
            frame[column] = ref.data[column].reset_index(drop=True)
        raw = {name: _sample(spec, rows, rng) for name, spec in parameters.columns.items()}
        steps = [
            TransformationStep(
                step="sample_marginals",
                details={
                    "rows": rows,
                    "distributions": {n: s.kind for n, s in parameters.columns.items()},
                },
            )
        ]
        if parameters.correlation is not None and rows > 1:
            _impose_rank_correlation(raw, parameters.correlation, rng)
            steps.append(
                TransformationStep(
                    step="rank_correlation",
                    details={
                        "method": "iman_conover",
                        "columns": list(parameters.correlation.columns),
                    },
                )
            )
        clipped: dict[str, JsonValue] = {}
        for name, spec in parameters.columns.items():
            if isinstance(spec, Categorical):
                frame[name] = raw[name]
                continue
            frame[name], count = _finish(raw[name], spec)
            if count:
                clipped[name] = count
        if clipped:
            steps.append(TransformationStep(step="clip", details={"clipped_values": clipped}))
        return GeneratedData(data=ordered(frame, schema), transformations=tuple(steps))


def _row_count(size: GenerationSize, ref: Dataset | None, params: StatisticalParameters) -> int:
    if params.copy_from_reference:
        if ref is None:
            raise GeneratorParameterError("statistical: copy_from_reference needs a reference")
        if size.rows is not None and size.rows != len(ref.data):
            raise GeneratorParameterError(
                f"statistical: size.rows={size.rows} but the reference has {len(ref.data)} rows"
            )
        return len(ref.data)
    if size.rows is None:
        raise GeneratorParameterError("statistical: set size.rows or copy_from_reference")
    return size.rows


def _sample(spec: Distribution, rows: int, rng: np.random.Generator) -> np.ndarray:
    match spec:
        case Normal(mean=mean, std=std):
            return rng.normal(mean, std, rows)
        case LogNormal(mean=mean, sigma=sigma):
            return rng.lognormal(mean, sigma, rows)
        case Gamma(shape=shape, scale=scale):
            return rng.gamma(shape, scale, rows)
        case Poisson(lam=lam):
            return rng.poisson(lam, rows).astype("float64")
        case NegativeBinomial(mean=mean, dispersion=k):
            return rng.negative_binomial(k, k / (k + mean), rows).astype("float64")
        case Uniform(low=low, high=high):
            return rng.uniform(low, high, rows)
        case Categorical(values=values, weights=weights):
            p = None if weights is None else np.asarray(weights) / sum(weights)
            return np.asarray(
                [values[i] for i in rng.choice(len(values), size=rows, p=p)], dtype=object
            )
    raise GeneratorParameterError(
        f"statistical: unsupported distribution {spec!r}"
    )  # pragma: no cover


def _impose_rank_correlation(
    raw: dict[str, np.ndarray], correlation: Correlation, rng: np.random.Generator
) -> None:
    columns = correlation.columns
    chol = np.linalg.cholesky(np.asarray(correlation.matrix, dtype=float))
    rows = len(raw[columns[0]])
    scores = rng.standard_normal((rows, len(columns))) @ chol.T
    for j, name in enumerate(columns):
        ranks = np.argsort(np.argsort(scores[:, j], kind="stable"), kind="stable")
        raw[name] = np.sort(raw[name], kind="stable")[ranks]


def _finish(values: np.ndarray, spec: NumericDistribution) -> tuple[pd.Series, int]:
    series = pd.Series(values, dtype="float64")
    low, high = spec.clip_min, spec.clip_max
    count = int(
        ((series < low).sum() if low is not None else 0)
        + ((series > high).sum() if high is not None else 0)
    )
    if low is not None or high is not None:
        series = series.clip(lower=low, upper=high)
    if spec.integer:
        return series.round().astype("int64"), count
    if spec.decimals is not None:
        series = series.round(spec.decimals)
    return series, count
