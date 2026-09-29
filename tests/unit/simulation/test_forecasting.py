"""Tests for the forecast plugins (TASK-FC-001 / TASK-FC-002)."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from industrial_ai.core.errors import SimulationInputError
from industrial_ai.foundation.datasets import (
    Dataset,
    DatasetBundle,
    DatasetSchema,
    DType,
    FieldSpec,
    SourceInfo,
    SourceType,
    build_dataset,
)
from industrial_ai.foundation.provenance import Lineage
from industrial_ai.simulation import (
    RunContext,
    SimulationEngine,
    SimulationPlugin,
    SimulationResult,
    new_simulation_registry,
)
from industrial_ai.simulation.forecasting import (
    LightGBMForecast,
    MovingAverageForecast,
    SeasonalNaiveForecast,
)

SCHEMA = DatasetSchema(
    schema_id="test.demand",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="date", dtype=DType.DATE),
        FieldSpec(name="item", dtype=DType.STR),
        FieldSpec(name="site", dtype=DType.STR),
        FieldSpec(name="quantity", dtype=DType.FLOAT, min=0),
    ),
    primary_key=("date", "item", "site"),
    time_index="date",
)
WEEKLY = np.array([3.0, 3.0, 3.0, 4.0, 5.0, 8.0, 9.0])  # Monday .. Sunday
START, END = date(2016, 1, 4), date(2016, 2, 14)  # Monday .. Sunday, 6 weeks
PARAMS = {"entity_columns": ["item", "site"]}
PLUGINS = ["seasonal_naive", "moving_average", "lightgbm"]


def series(days: int = 900, noise: bool = False, scale_after: date | None = None) -> Dataset:
    dates = pd.date_range(end=pd.Timestamp(END), periods=days, freq="D")
    rng = np.random.default_rng(0)
    parts = []
    for item, level in (("A", 1.0), ("B", 4.0)):
        values = level * WEEKLY[dates.dayofweek]
        if noise:
            values = rng.poisson(values).astype(float)
        if scale_after is not None:
            values = np.where(dates >= pd.Timestamp(scale_after), values * 3, values)
        parts.append(pd.DataFrame({"date": dates, "item": item, "site": "S1", "quantity": values}))
    return build_dataset(
        dataset_id="demand",
        version="1",
        schema=SCHEMA,
        data=pd.concat(parts, ignore_index=True),
        source=SourceInfo(name="demand", source_type=SourceType.FIXTURE),
        lineage=Lineage(),
    )


def engine() -> SimulationEngine:
    registry = new_simulation_registry()
    for plugin in (SeasonalNaiveForecast(), MovingAverageForecast(), LightGBMForecast()):
        registry.register(plugin)
    return SimulationEngine(registry)


def run(plugin: str, dataset: Dataset | DatasetBundle, **params: object) -> SimulationResult:
    context = RunContext(run_id="fc", seed=11, start_date=START, end_date=END)
    return engine().run(plugin, dataset, None, PARAMS | params, context)  # type: ignore[arg-type]


def prediction(result: SimulationResult) -> pd.DataFrame:
    assert result.prediction is not None
    return result.prediction.data


def metric(result: SimulationResult, metric_id: str) -> float:
    value = result.metric(metric_id).value
    assert value is not None
    return value


@pytest.mark.parametrize(
    "plugin", [SeasonalNaiveForecast(), MovingAverageForecast(), LightGBMForecast()]
)
def test_plugins_satisfy_protocol(plugin: SimulationPlugin) -> None:
    assert isinstance(plugin, SimulationPlugin)


@pytest.mark.parametrize("plugin", PLUGINS)
def test_rolling_layout(plugin: str) -> None:
    frame = prediction(run(plugin, series()))
    origins = sorted(frame["origin_date"].unique())
    assert [pd.Timestamp(o).date() for o in origins] == [
        date(2016, 1, 4) + pd.Timedelta(days=7 * k) for k in range(6)
    ]
    assert len(frame) == 6 * 28 * 2
    assert frame["forecast"].min() >= 0
    later = frame[frame["date"] > pd.Timestamp(END)]
    assert later["actual"].isna().all()  # beyond the observed data: no actual


@pytest.mark.parametrize("plugin", PLUGINS)
def test_no_look_ahead(plugin: str) -> None:
    """Changing data on or after an origin never changes forecasts made at that origin."""
    changed_from = date(2016, 1, 25)  # the 4th origin
    base = prediction(run(plugin, series(noise=True)))
    changed = prediction(run(plugin, series(noise=True, scale_after=changed_from)))
    early = base["origin_date"] <= pd.Timestamp(changed_from)
    pd.testing.assert_series_equal(base.loc[early, "forecast"], changed.loc[early, "forecast"])
    assert not base.loc[~early, "forecast"].equals(changed.loc[~early, "forecast"])


def test_seasonal_naive_reproduces_a_weekly_pattern_exactly() -> None:
    result = run("seasonal_naive", series())
    frame = prediction(result)
    expected = np.where(frame["item"] == "A", 1.0, 4.0) * WEEKLY[frame["date"].dt.dayofweek]
    np.testing.assert_allclose(frame["forecast"], expected)
    assert metric(result, "mae") == 0.0 and metric(result, "wape") == 0.0


def test_moving_average_is_flat_mean() -> None:
    frame = prediction(run("moving_average", series(), window_days=7))
    a = frame[(frame["item"] == "A")]
    assert np.allclose(a["forecast"], WEEKLY.mean())


def test_lightgbm_learns_the_weekly_pattern_and_is_reproducible() -> None:
    first = run("lightgbm", series(noise=True))
    second = run("lightgbm", series(noise=True))
    assert first.prediction is not None and second.prediction is not None
    assert first.prediction.metadata.content_hash == second.prediction.metadata.content_hash
    assert metric(first, "wape") < metric(run("moving_average", series(noise=True)), "wape")
    details = first.prediction.provenance.transformations[0].details["plugin_details"]
    assert isinstance(details, dict) and details["training_end"] == "2016-01-03"


def test_accuracy_metrics_definitions() -> None:
    frame = prediction(run("moving_average", series(), window_days=7))
    rows = frame.dropna(subset=["actual"])
    error = rows["forecast"] - rows["actual"]
    result = run("moving_average", series(), window_days=7)
    assert metric(result, "mae") == pytest.approx(error.abs().mean())
    assert metric(result, "rmse") == pytest.approx(np.sqrt((error**2).mean()))
    assert metric(result, "wape") == pytest.approx(error.abs().sum() / rows["actual"].sum())
    assert metric(result, "bias") == pytest.approx(error.sum() / rows["actual"].sum())


def test_wape_undefined_without_actuals() -> None:
    history_only = series(days=900)
    data = history_only.data[history_only.data["date"] < pd.Timestamp(START)]
    dataset = build_dataset(
        dataset_id="h",
        version="1",
        schema=SCHEMA,
        data=data,
        source=SourceInfo(name="h", source_type=SourceType.FIXTURE),
        lineage=Lineage(),
    )
    result = run("moving_average", dataset)
    assert (
        result.metric("wape").value is None and result.metric("forecast_rows_evaluated").value == 0
    )


def test_missing_observations_are_filled_and_reported() -> None:
    full = series()
    gappy = build_dataset(
        dataset_id="g",
        version="1",
        schema=SCHEMA,
        data=full.data.drop(index=[10, 11, 12]),
        source=SourceInfo(name="g", source_type=SourceType.FIXTURE),
        lineage=Lineage(),
    )
    result = run("moving_average", gappy)
    assert any("3 missing" in w for w in result.metadata.warnings)


def test_input_errors() -> None:
    bundle = DatasetBundle(
        "b", "1", {"sales": series()}, SourceInfo(name="b", source_type=SourceType.FIXTURE)
    )
    with pytest.raises(SimulationInputError, match="input_table"):
        run("moving_average", bundle)
    assert run("moving_average", bundle, input_table="sales").prediction is not None
    with pytest.raises(SimulationInputError, match="lacks columns"):
        run("moving_average", series(), value_column="units")
    with pytest.raises(SimulationInputError, match="at least"):
        run("lightgbm", series(days=60))
