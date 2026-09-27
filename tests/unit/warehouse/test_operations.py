"""Tests for synthetic warehouse operations and demand (TASK-WH-001, Gate 5)."""

from datetime import date
from pathlib import Path

import pytest

from industrial_ai.foundation.datasets import DatasetBundle, SourceType
from industrial_ai.foundation.validation import validate_bundle
from industrial_ai.scenario import ScenarioSpec
from industrial_ai_warehouse.adapters.m5 import M5Adapter
from industrial_ai_warehouse.generators import (
    DemandConfig,
    OperationsConfig,
    build_hybrid_bundle,
    generate_operations,
    generate_synthetic_demand,
)
from industrial_ai_warehouse.schemas import OPERATIONS_SCHEMAS

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "m5_like"
SEED = 20260927


@pytest.fixture(scope="module")
def retail() -> DatasetBundle:
    return M5Adapter().load(FIXTURE)


@pytest.fixture(scope="module")
def ops(retail: DatasetBundle) -> DatasetBundle:
    return generate_operations(retail, SEED)


def test_hybrid_bundle_is_valid(retail: DatasetBundle, ops: DatasetBundle) -> None:
    assert set(ops.tables) == set(OPERATIONS_SCHEMAS)
    report = validate_bundle(build_hybrid_bundle(retail, ops))
    assert report.passed, report.failures
    assert not report.skipped  # every foreign key resolved inside the hybrid bundle


def test_generation_is_reproducible(retail: DatasetBundle, ops: DatasetBundle) -> None:
    assert generate_operations(retail, SEED).content_hash == ops.content_hash
    assert generate_operations(retail, SEED + 1).content_hash != ops.content_hash


def test_structure_follows_the_single_echelon_model(
    retail: DatasetBundle, ops: DatasetBundle
) -> None:
    warehouses = ops.table("warehouse").data
    assert sorted(warehouses["store_id"]) == sorted(retail.table("store").data["store_id"])
    series = retail.table("sales").data[["product_id", "store_id"]].drop_duplicates()
    assert len(ops.table("initial_inventory").data) == len(series)
    assert set(ops.table("product_supplier").data["product_id"]) == set(
        retail.table("product").data["product_id"]
    )
    assert len(ops.table("supplier").data) == OperationsConfig().supplier_count


def test_derived_values_follow_their_rules(ops: DatasetBundle) -> None:
    cfg = OperationsConfig()
    plan = ops.table("planning_input").data
    inventory = ops.table("initial_inventory").data.merge(plan, on=["product_id", "warehouse_id"])
    expected = (
        inventory["mean_daily_demand"]
        * (inventory["lead_time_mean_days"] + cfg.order_cycle_days / 2)
    ).round()
    assert (inventory["on_hand_units"] == expected.astype("int64")).all()
    costs = ops.table("product_supplier").data.merge(
        ops.table("product_price").data, on="product_id"
    )
    assert (
        costs["unit_cost"] - (costs["avg_unit_price"] * cfg.cost_ratio).round(2)
    ).abs().max() < 1e-9
    lead = ops.table("supplier_lead_time").data
    assert (lead["lead_time_std_days"] <= lead["lead_time_mean_days"]).all()


def test_provenance_and_labels(retail: DatasetBundle, ops: DatasetBundle) -> None:
    assert ops.table("warehouse").metadata.source_type is SourceType.SYNTHETIC
    assert ops.table("planning_input").metadata.source_type is SourceType.DERIVED
    lead = ops.table("supplier_lead_time").provenance
    assert lead.component is not None and lead.component.id == "statistical"
    assert lead.inputs[0].content_hash == ops.table("supplier").metadata.content_hash
    assert ops.lineage.seed == SEED
    config = ops.lineage.parameters["config"]
    assert isinstance(config, dict) and config["cost_ratio"] == 0.7
    plan_inputs = {i.dataset_id for i in ops.table("planning_input").provenance.inputs}
    assert "m5_fixture.sales" in plan_inputs


def test_config_changes_the_environment(retail: DatasetBundle, ops: DatasetBundle) -> None:
    other = generate_operations(
        retail, SEED, OperationsConfig(supplier_count=2, order_cycle_days=7)
    )
    assert len(other.table("supplier").data) == 2
    assert other.table("initial_inventory").data["on_hand_units"].sum() < (
        ops.table("initial_inventory").data["on_hand_units"].sum()
    )


def spec(scenario_id: str, **parameters: float) -> ScenarioSpec:
    return ScenarioSpec(
        scenario_id=scenario_id,
        version="1.0.0",
        pack="warehouse",
        title=scenario_id,
        parameters=dict(parameters),
    )


def test_scenario_demand_effect_is_exact_without_noise(retail: DatasetBundle) -> None:
    config = DemandConfig(start=date(2014, 2, 1), periods=91)
    base = generate_synthetic_demand(retail, config, SEED, spec("baseline", noise_scale=0.0))
    high = generate_synthetic_demand(
        retail,
        config,
        SEED,
        spec("high_demand", demand_multiplier=1.3, noise_scale=0.0, lead_time_delta=0),
    )
    ratio = high.data["quantity"].sum() / base.data["quantity"].sum()
    assert ratio == pytest.approx(1.3, abs=0.01)  # rounding of daily rates only
    assert (high.data["scenario_id"] == "high_demand").all()
    assert any("lead_time_delta" in w for w in high.warnings)
    assert high.dataset_id != base.dataset_id


def test_scenario_demand_is_reproducible_and_labelled(retail: DatasetBundle) -> None:
    config = DemandConfig(start=date(2014, 2, 1), periods=91)
    base = generate_synthetic_demand(retail, config, SEED)
    assert (base.data["scenario_id"] == "none").all()
    assert (
        generate_synthetic_demand(retail, config, SEED).metadata.content_hash
        == base.metadata.content_hash
    )
    assert (
        generate_synthetic_demand(retail, config, SEED + 1).metadata.content_hash
        != base.metadata.content_hash
    )
