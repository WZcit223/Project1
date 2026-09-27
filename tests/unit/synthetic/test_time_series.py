"""Tests for the time_series generator (TASK-SYN-005)."""

from collections.abc import Mapping
from datetime import date

import numpy as np
import pandas as pd
import pytest
from pydantic import JsonValue

from industrial_ai.core.errors import GeneratorParameterError
from industrial_ai.foundation.datasets import (
    Dataset,
    DatasetSchema,
    DType,
    FieldSpec,
    SourceInfo,
    SourceType,
    build_dataset,
)
from industrial_ai.foundation.provenance import Lineage
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.synthetic import (
    GenerationRequest,
    GenerationSize,
    SyntheticDataGenerator,
    SyntheticDataset,
    SyntheticEngine,
    new_generator_registry,
)
from industrial_ai.synthetic.generators import TimeSeriesGenerator

SCHEMA = DatasetSchema(
    schema_id="test.demand",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="date", dtype=DType.DATE),
        FieldSpec(name="item", dtype=DType.STR),
        FieldSpec(name="site", dtype=DType.STR),
        FieldSpec(name="quantity", dtype=DType.INT, min=0),
        FieldSpec(name="scenario_id", dtype=DType.STR),
    ),
    primary_key=("date", "item", "site"),
    time_index="date",
    entity_keys=("item", "site"),
)
WEEKLY = [0.8, 0.8, 0.8, 0.8, 1.0, 1.4, 1.4]  # Mon..Sun, mean 1
FLAT_PROFILES = [
    {"entity": {"item": "A", "site": "S1"}, "level": 10.0},
    {"entity": {"item": "B", "site": "S1"}, "level": 4.0},
]
START = date(2016, 1, 4)  # a Monday


def scenario(**parameters: float) -> ScenarioSpec:
    values: dict[str, JsonValue] = dict(parameters)
    return ScenarioSpec(
        scenario_id="test", version="1.0.0", pack="test", title="t", parameters=values
    )


def base_params(**overrides: object) -> dict[str, object]:
    params: dict[str, object] = {
        "entity_columns": ["item", "site"],
        "calibration": "none",
        "profiles": FLAT_PROFILES,
        "scenario_id_column": "scenario_id",
    }
    return params | overrides


def generate(
    params: Mapping[str, object],
    *,
    spec: ScenarioSpec | None = None,
    seed: int = 1,
    periods: int = 28,
    reference: Dataset | None = None,
) -> SyntheticDataset:
    registry = new_generator_registry()
    registry.register(TimeSeriesGenerator())
    request = GenerationRequest(
        generator_id="time_series",
        dataset_id="demand",
        output_schema=SCHEMA,
        scenario=spec,
        seed=seed,
        size=GenerationSize(start=START, periods=periods),
        parameters=dict(params),  # type: ignore[arg-type]
    )
    return SyntheticEngine(registry).generate(request, reference=reference)


def exact(params: Mapping[str, object], spec: ScenarioSpec | None = None) -> pd.DataFrame:
    """Noise off: output equals the expected rate (rounded)."""
    effects = dict(spec.parameters) if spec else {}
    return generate(params, spec=scenario(noise_scale=0.0, **effects)).data  # type: ignore[arg-type]


def item(frame: pd.DataFrame, name: str) -> pd.Series:
    return frame.loc[frame["item"] == name, "quantity"].reset_index(drop=True)


def test_is_a_generator() -> None:
    assert isinstance(TimeSeriesGenerator(), SyntheticDataGenerator)


def test_output_layout() -> None:
    data = generate(base_params()).data
    assert len(data) == 2 * 28
    assert list(data.columns) == list(SCHEMA.field_names)
    assert (data["scenario_id"] == "none").all()
    assert data["date"].is_monotonic_increasing


def test_level_multiplier_and_noise_off_are_exact() -> None:
    assert (item(exact(base_params()), "A") == 10).all()
    high = exact(base_params(), scenario(level_multiplier=1.3))
    assert (item(high, "A") == 13).all()


def test_shock_window() -> None:
    data = exact(
        base_params(), scenario(shock_multiplier=2.5, shock_start_day=7, shock_duration_days=5)
    )
    a = item(data, "A")
    assert (a[7:12] == 25).all()
    assert (a[:7] == 10).all() and (a[12:] == 10).all()


def test_seasonality_multiplier_scales_weekly_pattern() -> None:
    profiles = [FLAT_PROFILES[0] | {"weekly": WEEKLY}]
    params = base_params(profiles=profiles)
    normal = item(exact(params), "A")
    assert normal[:7].tolist() == [8, 8, 8, 8, 10, 14, 14]
    flat = item(exact(params, scenario(seasonality_multiplier=0.0)), "A")
    assert (flat == 10).all()
    strong = item(exact(params, scenario(seasonality_multiplier=2.0)), "A")
    assert strong[:7].tolist() == [6, 6, 6, 6, 10, 18, 18]


def test_negative_binomial_noise_matches_mean_and_variance() -> None:
    params = base_params(
        profiles=[{"entity": {"item": "A", "site": "S1"}, "level": 20.0, "dispersion": 4.0}]
    )
    values = generate(params, periods=20_000).data["quantity"]
    assert values.mean() == pytest.approx(20.0, rel=0.03)
    assert values.var() == pytest.approx(20.0 + 400.0 / 4.0, rel=0.08)


def test_reproducible_and_seed_sensitive() -> None:
    a, b, c = (
        generate(base_params(), seed=5),
        generate(base_params(), seed=5),
        generate(base_params(), seed=6),
    )
    assert a.metadata.content_hash == b.metadata.content_hash != c.metadata.content_hash


def test_scenario_mapping_and_unused_parameter_warnings() -> None:
    spec = ScenarioSpec(
        scenario_id="high_demand",
        version="1.0.0",
        pack="warehouse",
        title="High demand",
        parameters={"demand_multiplier": 1.3, "noise_scale": 0.0, "lead_time_delta": 0},
    )
    result = generate(
        base_params(scenario_mapping={"level_multiplier": "demand_multiplier"}), spec=spec
    )
    assert (item(result.data, "A") == 13).all()
    assert (result.data["scenario_id"] == "high_demand").all()
    assert any("lead_time_delta" in w for w in result.warnings)
    assert not any("demand_multiplier" in w for w in result.warnings)
    assert result.provenance.scenario is not None


def history(days: int = 730, launch_day: int = 200, seed: int = 0) -> Dataset:
    """Reference with a known weekly pattern; item B launches late (leading zeros)."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2014-01-06", periods=days, freq="D")  # Monday start
    rows = []
    for name, level in (("A", 12.0), ("B", 5.0)):
        rate = level * np.asarray(WEEKLY)[dates.dayofweek]
        values = rng.poisson(rate)
        if name == "B":
            values[:launch_day] = 0
        rows.append(pd.DataFrame({"date": dates, "item": name, "site": "S1", "quantity": values}))
    frame = pd.concat(rows, ignore_index=True).assign(scenario_id="reference")
    return build_dataset(
        dataset_id="history",
        version="1",
        schema=SCHEMA,
        data=frame,
        source=SourceInfo(name="history", source_type=SourceType.FIXTURE),
        lineage=Lineage(),
    )


def calibrated_params(**overrides: object) -> dict[str, object]:
    return {
        "entity_columns": ["item", "site"],
        "scenario_id_column": "scenario_id",
        "history_window_days": None,
    } | overrides


def test_calibration_recovers_level_and_weekly_pattern() -> None:
    result = generate(calibrated_params(), reference=history(), periods=7 * 400, seed=3)
    data = result.data
    a, b = data[data["item"] == "A"], data[data["item"] == "B"]
    assert a["quantity"].mean() == pytest.approx(12.0, rel=0.05)
    # leading zeros before B's launch are excluded, so B's level is not diluted
    assert b["quantity"].mean() == pytest.approx(5.0, rel=0.07)
    weekday_ratio = a.groupby(a["date"].dt.dayofweek)["quantity"].mean() / a["quantity"].mean()
    assert weekday_ratio[5] == pytest.approx(1.4, rel=0.06) and weekday_ratio[0] == pytest.approx(
        0.8, rel=0.06
    )
    step = result.provenance.transformations[0]
    assert step.step == "calibrate" and step.details["leading_zeros_excluded"] is True
    assert result.provenance.inputs[0].dataset_id == "history"


def test_calibration_is_deterministic() -> None:
    ref = history()
    first = generate(calibrated_params(), reference=ref, seed=9)
    second = generate(calibrated_params(), reference=ref, seed=9)
    assert first.metadata.content_hash == second.metadata.content_hash


def test_series_without_sales_generate_zero_with_warning() -> None:
    ref = history()
    silent = ref.data.assign(quantity=np.where(ref.data["item"] == "B", 0, ref.data["quantity"]))
    reference = build_dataset(
        dataset_id="history",
        version="1",
        schema=SCHEMA,
        data=silent,
        source=SourceInfo(name="h", source_type=SourceType.FIXTURE),
        lineage=Lineage(),
    )
    result = generate(calibrated_params(), reference=reference)
    assert (item(result.data, "B") == 0).all()
    assert any("no sales" in w for w in result.warnings)


@pytest.mark.parametrize(
    ("params", "message"),
    [
        (base_params(scenario_mapping={"bogus": "x"}), "unknown scenario effects"),
        (base_params(profiles=[]), "requires profiles"),
        (calibrated_params(), "needs a reference"),
        (base_params(entity_columns=["item"]), "columns do not match"),
    ],
    ids=["bad-mapping", "no-profiles", "no-reference", "schema-mismatch"],
)
def test_invalid_configuration(params: dict[str, object], message: str) -> None:
    with pytest.raises(GeneratorParameterError, match=message):
        generate(params)


def test_invalid_scenario_value_raises() -> None:
    with pytest.raises(GeneratorParameterError, match="invalid scenario values"):
        generate(base_params(), spec=scenario(level_multiplier=-1.0))
