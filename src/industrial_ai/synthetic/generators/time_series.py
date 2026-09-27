"""Time-series generator ``time_series`` 1.0.0 (docs/synthetic-data-api.md §6.3).

Daily count series per entity (e.g. product × store)::

    rate_t  = level · season_t · event_t · level_multiplier · shock_t
    season_t = max(0, 1 + seasonality_multiplier · (weekly[dow_t] · monthly[month_t] − 1))
    y_t ~ NegativeBinomial(mean = rate_t, dispersion = φ / noise_scale²)   (or Poisson)

Series profiles (level, weekly and monthly factors, dispersion) come either from explicit
``profiles`` or from **per-series calibration** on a reference history. Calibration ignores each
series' leading zeros (days before its first sale are "not yet available", not zero demand).

Scenario effects use generic names; ``scenario_mapping`` maps them to a scenario's parameter names
(e.g. ``{"level_multiplier": "demand_multiplier"}``). Effects are applied only when present in the
scenario, and the applied names are reported so the engine can flag unused ones.
"""

from datetime import date
from typing import Literal, Self

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

SCENARIO_EFFECTS = frozenset(
    {
        "level_multiplier",
        "seasonality_multiplier",
        "noise_scale",
        "shock_multiplier",
        "shock_start_day",
        "shock_duration_days",
    }
)
_POISSON_DISPERSION = 1e6
"""Dispersion used when the data show no over-dispersion (negative binomial ≈ Poisson)."""


class SeriesProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entity: dict[str, str]
    level: float = Field(ge=0)
    weekly: tuple[float, ...] = (1.0,) * 7
    """Monday … Sunday factors (mean 1)."""
    monthly: tuple[float, ...] = (1.0,) * 12
    """January … December factors (mean 1)."""
    dispersion: float = Field(default=10.0, gt=0)

    @model_validator(mode="after")
    def _shapes(self) -> Self:
        if len(self.weekly) != 7 or len(self.monthly) != 12:
            raise ValueError("weekly needs 7 factors and monthly 12")
        if min(self.weekly) < 0 or min(self.monthly) < 0:
            raise ValueError("seasonal factors must be >= 0")
        return self


class TimeSeriesParameters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_columns: tuple[str, ...] = Field(min_length=1)
    time_column: str = "date"
    value_column: str = "quantity"
    distribution: Literal["negative_binomial", "poisson"] = "negative_binomial"
    calibration: Literal["per_series", "none"] = "per_series"
    history_window_days: int | None = Field(default=730, ge=28)
    """Calibrate on the last N days of the reference (``None`` = all)."""
    profiles: tuple[SeriesProfile, ...] = ()
    """Explicit profiles (required when ``calibration="none"``)."""
    reference_table: str | None = None
    event_dates: tuple[date, ...] = ()
    event_multiplier: float = Field(default=1.0, ge=0)
    scenario_mapping: dict[str, str] = Field(default_factory=dict)
    """Generic effect name → scenario parameter name."""
    constant_columns: dict[str, JsonValue] = Field(default_factory=dict)
    scenario_id_column: str | None = None
    """Output column filled with the scenario id (``"none"`` without a scenario)."""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        unknown = sorted(set(self.scenario_mapping) - SCENARIO_EFFECTS)
        if unknown:
            raise ValueError(
                f"unknown scenario effects {unknown}; known: {sorted(SCENARIO_EFFECTS)}"
            )
        if self.calibration == "none" and not self.profiles:
            raise ValueError("calibration='none' requires profiles")
        if self.calibration == "per_series" and self.profiles:
            raise ValueError("give either profiles or per-series calibration, not both")
        return self


class _Effects(BaseModel):
    level_multiplier: float = Field(default=1.0, ge=0)
    seasonality_multiplier: float = Field(default=1.0, ge=0)
    noise_scale: float = Field(default=1.0, ge=0)
    shock_multiplier: float = Field(default=1.0, ge=0)
    shock_start_day: int = Field(default=0, ge=0)
    shock_duration_days: int = Field(default=0, ge=0)


class TimeSeriesGenerator:
    generator_id = "time_series"
    generator_version = "1.0.0"
    description = (
        "Daily count series per entity with level, weekly/monthly seasonality, events, noise and "
        "scenario effects; calibrated per series from reference history."
    )
    parameter_model: type[BaseModel] = TimeSeriesParameters
    scenario_parameters: frozenset[str] = SCENARIO_EFFECTS

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
        if not isinstance(parameters, TimeSeriesParameters):
            raise GeneratorParameterError("time_series expects TimeSeriesParameters")
        p = parameters
        extra_columns = [
            *p.constant_columns,
            *([p.scenario_id_column] if p.scenario_id_column else []),
        ]
        check_columns(
            [p.time_column, *p.entity_columns, p.value_column, *extra_columns],
            schema,
            self.generator_id,
        )
        if size.start is None or size.periods is None:
            raise GeneratorParameterError("time_series: size.start and size.periods are required")

        steps: list[TransformationStep] = []
        warnings: list[str] = []
        if p.calibration == "per_series":
            ref = reference_table(reference, p.reference_table, self.generator_id)
            if ref is None:
                raise GeneratorParameterError(
                    "time_series: per_series calibration needs a reference"
                )
            profiles, calibration_step = calibrate(ref.data, p)
            steps.append(calibration_step)
            zero = [prof.entity for prof in profiles if prof.level == 0]
            if zero:
                warnings.append(
                    f"{len(zero)} series have no sales in the calibration window; generated as 0"
                )
        else:
            profiles = sorted(
                p.profiles, key=lambda prof: tuple(prof.entity[c] for c in p.entity_columns)
            )

        effects, applied = _effects(scenario, p)
        if p.distribution == "poisson" and effects.noise_scale != 1.0:
            applied.discard(p.scenario_mapping.get("noise_scale", "noise_scale"))
            warnings.append("noise_scale is only applied with the negative_binomial distribution")
            effects = effects.model_copy(update={"noise_scale": 1.0})

        dates = pd.date_range(size.start, periods=size.periods, freq="D")
        frame, clipped = _simulate(profiles, dates, p, effects, seed)
        for column, value in p.constant_columns.items():
            frame[column] = pd.Series([value] * len(frame), index=frame.index, dtype="object")
        if p.scenario_id_column:
            frame[p.scenario_id_column] = scenario.scenario_id if scenario else "none"

        steps.append(
            TransformationStep(
                step="simulate_series",
                details={
                    "series": len(profiles),
                    "start": dates[0].date().isoformat(),
                    "periods": len(dates),
                    "distribution": p.distribution,
                    "effects": effects.model_dump(),
                    "seasonal_rates_clipped_at_zero": clipped,
                },
            )
        )
        return GeneratedData(
            data=ordered(frame, schema),
            transformations=tuple(steps),
            warnings=tuple(warnings),
            applied_scenario_parameters=frozenset(applied),
        )


def _effects(scenario: ScenarioSpec | None, p: TimeSeriesParameters) -> tuple[_Effects, set[str]]:
    if scenario is None:
        return _Effects(), set()
    values: dict[str, object] = {}
    applied: set[str] = set()
    for effect in SCENARIO_EFFECTS:
        name = p.scenario_mapping.get(effect, effect)
        if name in scenario.parameters:
            values[effect] = scenario.parameters[name]
            applied.add(name)
    try:
        return _Effects.model_validate(values), applied
    except ValueError as exc:
        raise GeneratorParameterError(f"time_series: invalid scenario values: {exc}") from exc


def calibrate(
    history: pd.DataFrame, p: TimeSeriesParameters
) -> tuple[list[SeriesProfile], TransformationStep]:
    """Estimate one :class:`SeriesProfile` per series from a daily history."""
    needed = [p.time_column, *p.entity_columns, p.value_column]
    missing = sorted(set(needed) - set(history.columns))
    if missing:
        raise GeneratorParameterError(f"time_series: reference lacks columns {missing}")
    data = history[needed].copy()
    data[p.time_column] = pd.to_datetime(data[p.time_column])
    end = data[p.time_column].max()
    window_start = (
        data[p.time_column].min()
        if p.history_window_days is None
        else end - pd.Timedelta(days=p.history_window_days - 1)
    )
    profiles: list[SeriesProfile] = []
    for key, series in data.groupby(list(p.entity_columns), sort=True):
        keys = key if isinstance(key, tuple) else (key,)
        entity = {c: str(v) for c, v in zip(p.entity_columns, keys, strict=True)}
        profiles.append(_profile(entity, series, p, window_start))
    step = TransformationStep(
        step="calibrate",
        details={
            "method": "per_series",
            "window_start": window_start.date().isoformat(),
            "window_end": end.date().isoformat(),
            "series": len(profiles),
            "leading_zeros_excluded": True,
            "mean_level": round(float(np.mean([pr.level for pr in profiles])), 6)
            if profiles
            else 0.0,
        },
    )
    return profiles, step


def _profile(
    entity: dict[str, str],
    series: pd.DataFrame,
    p: TimeSeriesParameters,
    window_start: pd.Timestamp,
) -> SeriesProfile:
    times, values = series[p.time_column], series[p.value_column].astype("float64")
    sold = times[values > 0]
    if sold.empty:
        return SeriesProfile(entity=entity, level=0.0)
    active = (times >= max(sold.min(), window_start)).to_numpy()
    t, y = times[active], values[active]
    level = float(y.mean())
    if level == 0:
        return SeriesProfile(entity=entity, level=0.0)
    weekly = _normalised(y.groupby(t.dt.dayofweek).mean(), range(7), level)
    monthly = _normalised(y.groupby(t.dt.month).mean(), range(1, 13), level)
    fitted = level * np.asarray(weekly)[t.dt.dayofweek] * np.asarray(monthly)[t.dt.month - 1]
    excess = float(((y.to_numpy() - fitted) ** 2 - fitted).sum())
    dispersion = (
        float(np.clip((fitted**2).sum() / excess, 0.05, _POISSON_DISPERSION))
        if excess > 0
        else _POISSON_DISPERSION
    )
    return SeriesProfile(
        entity=entity,
        level=round(level, 6),
        weekly=weekly,
        monthly=monthly,
        dispersion=round(dispersion, 6),
    )


def _normalised(means: pd.Series, keys: range, level: float) -> tuple[float, ...]:
    """Factors relative to ``level`` for each key; missing keys get 1; present keys average to 1."""
    factors = {k: float(means[k]) / level for k in keys if k in means.index}
    if factors:
        scale = float(np.mean(list(factors.values())))
        factors = {k: v / scale for k, v in factors.items()} if scale > 0 else factors
    return tuple(round(factors.get(k, 1.0), 6) for k in keys)


def _simulate(
    profiles: list[SeriesProfile],
    dates: pd.DatetimeIndex,
    p: TimeSeriesParameters,
    effects: _Effects,
    seed: int,
) -> tuple[pd.DataFrame, int]:
    dow = dates.dayofweek.to_numpy()
    month = dates.month.to_numpy() - 1
    day = np.arange(len(dates))
    shock = np.where(
        (day >= effects.shock_start_day)
        & (day < effects.shock_start_day + effects.shock_duration_days),
        effects.shock_multiplier,
        1.0,
    )
    events = np.where(
        dates.normalize().isin(pd.to_datetime(list(p.event_dates))), p.event_multiplier, 1.0
    )
    children = np.random.SeedSequence(seed).spawn(len(profiles))
    parts, clipped = [], 0
    for profile, child in zip(profiles, children, strict=True):
        pattern = np.asarray(profile.weekly)[dow] * np.asarray(profile.monthly)[month]
        season = 1.0 + effects.seasonality_multiplier * (pattern - 1.0)
        clipped += int((season < 0).sum())
        rate = profile.level * np.maximum(season, 0.0) * events * effects.level_multiplier * shock
        values = _sample(
            rate,
            profile.dispersion,
            p.distribution,
            effects.noise_scale,
            np.random.default_rng(child),
        )
        part = pd.DataFrame({p.time_column: dates, p.value_column: values})
        for column in p.entity_columns:
            part[column] = profile.entity[column]
        parts.append(part)
    if not parts:
        raise GeneratorParameterError("time_series: no series to generate")
    frame = pd.concat(parts, ignore_index=True)
    frame = frame.sort_values([p.time_column, *p.entity_columns], kind="stable").reset_index(
        drop=True
    )
    return frame, clipped


def _sample(
    rate: np.ndarray,
    dispersion: float,
    distribution: str,
    noise_scale: float,
    rng: np.random.Generator,
) -> np.ndarray:
    if noise_scale == 0:
        exact: np.ndarray = np.rint(rate).astype("int64")
        return exact
    if distribution == "poisson":
        counts: np.ndarray = rng.poisson(rate).astype("int64")
        return counts
    k = dispersion / noise_scale**2
    safe = np.where(rate > 0, rate, 1.0)
    draws = rng.negative_binomial(k, k / (k + safe))
    result: np.ndarray = np.where(rate > 0, draws, 0).astype("int64")
    return result
