"""Checks against the owner's real M5 subset in data/reference/m5_subset/ (owner-approved commit).

Select with ``uv run pytest -m m5_local``; skipped if the folder is absent.
"""

from pathlib import Path

import pytest

from industrial_ai.foundation.validation import validate_bundle
from industrial_ai_warehouse.adapters.m5 import M5Adapter

SUBSET_DIR = Path(__file__).resolve().parents[2] / "data" / "reference" / "m5_subset"

pytestmark = [
    pytest.mark.m5_local,
    pytest.mark.skipif(not SUBSET_DIR.is_dir(), reason="no M5 subset in data/reference/m5_subset"),
]


def test_real_m5_subset_converts_and_validates() -> None:
    bundle = M5Adapter().load(SUBSET_DIR)
    report = validate_bundle(bundle)
    assert report.passed, report.failures
    assert not report.skipped


def test_real_m5_subset_hybrid_environment_is_valid() -> None:
    from industrial_ai_warehouse.generators import build_hybrid_bundle, generate_operations

    retail = M5Adapter().load(SUBSET_DIR)
    report = validate_bundle(build_hybrid_bundle(retail, generate_operations(retail, seed=1)))
    assert report.passed, report.failures
    assert not report.skipped


def test_forecast_plugins_run_on_real_subset() -> None:
    """All three forecasters run on 26 rolling origins; LightGBM beats the moving average (WAPE)."""
    from datetime import date

    from pydantic import JsonValue

    from industrial_ai.simulation import RunContext, SimulationEngine, new_simulation_registry
    from industrial_ai.simulation.forecasting import (
        LightGBMForecast,
        MovingAverageForecast,
        SeasonalNaiveForecast,
    )

    registry = new_simulation_registry()
    for plugin in (SeasonalNaiveForecast(), MovingAverageForecast(), LightGBMForecast()):
        registry.register(plugin)
    engine = SimulationEngine(registry)
    bundle = M5Adapter().load(SUBSET_DIR)
    context = RunContext(
        run_id="m5", seed=1, start_date=date(2015, 11, 23), end_date=date(2016, 5, 22)
    )
    params: dict[str, JsonValue] = {
        "entity_columns": ["product_id", "store_id"],
        "input_table": "sales",
    }
    wape = {}
    for plugin_id in ("seasonal_naive", "moving_average", "lightgbm"):
        value = engine.run(plugin_id, bundle, None, params, context).metric("wape").value
        assert value is not None
        wape[plugin_id] = value
    assert wape["lightgbm"] < wape["moving_average"]
