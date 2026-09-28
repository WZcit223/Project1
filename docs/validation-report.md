# Validation Report — v0.1

Generated 2026-09-28 09:16 UTC by `scripts/validation_report.py` from commit `dc940f7` on branch `phase14`. Python 3.11.15, pandas 3.0.6, numpy 2.4.6, lightgbm 4.7.0; seed 20260927. Categories as defined in [validation.md §1](validation.md#1-validation-categories).

> **Claim.** *The framework validates synthetic data generation and scenario execution at
> the prototype level.* No claim is made that synthetic data, forecasts or strategy
> results represent a real warehouse: real operational validation (V4) was **not**
> performed.

## Summary

| Category | Evidence | Result |
|---|---|---|
| **V1** Software / framework correctness | 314 tests: 314 passed, 0 failed, 0 skipped | ✅ pass |
| **V2** Framework integration / Golden Path | 49 tests: 49 passed, 0 failed, 0 skipped | ✅ pass |
| **V3** Scenario & reference-data validation | 13 tests: 13 passed, 0 failed, 0 skipped | ✅ pass |
| **V3** reference data (descriptive) | M5 subset: data checks 279 passed / 0 failed; calibration comparison, forecast backtest, Golden Path smoke run (§3.2) | ✅ checks pass; comparisons descriptive |
| **V4** Real operational validation | — | ⛔ not performed (future) |

## 1. V1 — Software / framework correctness

Unit and contract tests of every layer; architecture import rules (the framework never imports packs, layer dependencies, the UI imports no framework module); synthetic-data structure (schema, constraints, relationships, reproducibility, provenance); metric definitions; failure modes.

`uv run pytest tests/unit -m "not m5_local"` — 22 s

| Test module | Tests |
|---|---|
| `tests/unit/application/test_runner.py` | 14 |
| `tests/unit/core/test_config.py` | 7 |
| `tests/unit/core/test_logging.py` | 3 |
| `tests/unit/core/test_registry.py` | 9 |
| `tests/unit/core/test_versioning.py` | 10 |
| `tests/unit/foundation/test_catalog.py` | 11 |
| `tests/unit/foundation/test_datasets.py` | 22 |
| `tests/unit/foundation/test_hashing.py` | 13 |
| `tests/unit/foundation/test_ingestion.py` | 12 |
| `tests/unit/foundation/test_provenance.py` | 3 |
| `tests/unit/foundation/test_validation.py` | 22 |
| `tests/unit/scenario/test_registry_and_loading.py` | 12 |
| `tests/unit/simulation/test_engine.py` | 8 |
| `tests/unit/simulation/test_forecasting.py` | 16 |
| `tests/unit/synthetic/test_engine.py` | 10 |
| `tests/unit/synthetic/test_rule_based.py` | 8 |
| `tests/unit/synthetic/test_statistical.py` | 10 |
| `tests/unit/synthetic/test_time_series.py` | 16 |
| `tests/unit/test_architecture.py` | 15 |
| `tests/unit/test_package.py` | 9 |
| `tests/unit/test_validation_report.py` | 3 |
| `tests/unit/warehouse/test_demand_timeline.py` | 2 |
| `tests/unit/warehouse/test_failure_modes.py` | 13 |
| `tests/unit/warehouse/test_inventory_simulation.py` | 12 |
| `tests/unit/warehouse/test_m5_adapter.py` | 15 |
| `tests/unit/warehouse/test_m5_fixture.py` | 3 |
| `tests/unit/warehouse/test_m5_subset.py` | 6 |
| `tests/unit/warehouse/test_m5_subset_standalone.py` | 1 |
| `tests/unit/warehouse/test_operations.py` | 8 |
| `tests/unit/warehouse/test_retail_schemas.py` | 3 |
| `tests/unit/warehouse/test_scenarios.py` | 5 |
| `tests/unit/warehouse/test_strategies.py` | 10 |
| `tests/unit/warehouse/test_strategy_base.py` | 3 |

## 2. V2 — Framework integration / Golden Path

End to end on the M5-shaped test fixture: canonical data → synthetic data → forecast → inventory × strategies × scenarios → metrics, through the workflow runner, the HTTP Application API and the browser UI; persisted datasets with verified hashes; provenance; reproducibility; no look-ahead; error handling.

`uv run pytest tests/integration tests/scenario/test_golden_path.py tests/ui -m "not m5_local"` — 97 s

| Test module | Tests |
|---|---|
| `tests/integration/test_api_golden_path.py` | 9 |
| `tests/integration/test_api_health.py` | 3 |
| `tests/integration/test_dataset_foundation.py` | 1 |
| `tests/integration/test_inventory_pipeline.py` | 2 |
| `tests/integration/test_no_look_ahead.py` | 1 |
| `tests/integration/test_strategy_comparison.py` | 3 |
| `tests/integration/test_synthetic_engine.py` | 1 |
| `tests/scenario/test_golden_path.py` | 18 |
| `tests/ui/test_ui.py` | 10 |
| `tests/ui/test_ui_stub_api.py` | 1 |

## 3. V3 — Scenario & reference-data validation

### 3.1 Tests

Scenario behaviour checks (docs/validation.md §4) on the fixture, and tests on the committed M5 reference subset; descriptive reference-data results follow in §3.2.

`uv run pytest tests/scenario/test_warehouse_scenarios.py tests/integration/test_m5_local.py` — 18 s

| Test module | Tests |
|---|---|
| `tests/integration/test_m5_local.py` | 3 |
| `tests/scenario/test_warehouse_scenarios.py` | 10 |

### 3.2 Reference data: the committed M5 subset

**What M5 is here.** Store-level retail **sales** (Walmart store CA_1, department FOODS_3, top 50 items) with calendar and prices. It is the **reference demand/sales environment**: synthetic demand is calibrated on it and forecasts are backtested on it. It is **not** warehouse operational data — warehouses, suppliers, lead times, costs, initial inventory and purchase orders are all **synthetic** (the Hybrid Validation Environment).

Source: M5 Forecasting Accuracy subset (stores=CA_1; departments=FOODS_3; categories=all; top_n=50) (https://www.kaggle.com/competitions/m5-forecasting-accuracy/data), downloaded 2026-09-20. Kaggle competition data: competition rules apply; do not redistribute. 50 series, 2011-01-29 … 2016-05-22.

| Data check | Passed | Failed | Skipped |
|---|---|---|---|
| Canonical retail bundle from the M5 adapter (schema, constraints, keys) | 85 | 0 | 0 |
| Hybrid environment: reference + synthetic operations (seed 20260927) | 194 | 0 | 0 |

**Calibration comparison** (descriptive, no pass/fail): last 365 days of reference sales vs. 91 days of synthetic baseline demand (time_series generator, seed 20260927).

| Statistic | Reference sales | Synthetic demand |
|---|---|---|
| Series | 50 | 50 |
| Mean units per series-day | 14.626 | 18.239 |
| Mean units per series-day with sales > 0 | 17.477 | 18.745 |
| Coefficient of variation of daily totals | 0.261 | 0.230 |
| Share of zero series-days | 16.3% | 2.7% |
| Weekday index (daily mean ÷ overall mean) | Mon 0.942, Tue 0.854, Wed 0.818, Thu 0.824, Fri 0.961, Sat 1.256, Sun 1.337 | Mon 0.915, Tue 0.839, Wed 0.837, Thu 0.814, Fri 0.97, Sat 1.244, Sun 1.38 |
| Correlation of per-item mean units | — | 0.905 |

Reading: synthetic mean demand is +25% versus the reference mean. The reference has 16.3% zero-sales series-days, the synthetic data 2.7%; on days with sales the means are close (17.477 vs. 18.745), so the gap comes mostly from zero observed sales that the generator does not reproduce. Zero observed sales in the M5 reference may reflect true zero demand, stockouts or other forms of demand censoring; the reference dataset does not provide sufficient inventory information to distinguish these causes directly (zero observed sales ≠ confirmed stockout). Per-item levels are strongly correlated and the weekday pattern is reproduced. The synthetic horizon (after the reference data) and the reference year cover different seasons. Zero-run modelling is on the roadmap (P1).

**Forecast backtest on reference sales** (weekly origins 2015-11-23 … 2016-05-22, 28-day horizon, history strictly before each origin):

| Model | WAPE | MAE (units) | Bias |
|---|---|---|---|
| `seasonal_naive` | 0.443 | 6.034 | -2.2% |
| `moving_average` | 0.459 | 6.261 | -2.2% |
| `lightgbm` | 0.413 | 5.628 | 0.8% |

**Golden Path smoke run on the reference subset** (workflow runner; 91-day synthetic horizon; seasonal-naive forecast; seed 20260927). A repeated baseline run reproduced identical metrics: **yes**. Descriptive only — not evidence that any strategy is better in reality.

| Scenario | Strategy | Fill rate | Stockout-day rate | Ordering cost | Holding cost | Lost-sales cost | Total cost |
|---|---|---|---|---|---|---|---|
| baseline | reorder_point | 84.7% | 15.0% | $17,917 | $444 | $20,887 | $39,248 |
| baseline | safety_stock | 86.2% | 12.0% | $18,827 | $574 | $17,595 | $36,995 |
| baseline | dynamic | 93.8% | 5.3% | $17,796 | $829 | $10,512 | $29,136 |
| high_demand | reorder_point | 74.3% | 24.6% | $20,381 | $367 | $49,282 | $70,030 |
| high_demand | safety_stock | 76.9% | 18.9% | $20,922 | $499 | $41,445 | $62,865 |
| high_demand | dynamic | 89.9% | 8.5% | $17,612 | $1,002 | $21,252 | $39,865 |
| demand_shock | reorder_point | 74.3% | 21.1% | $18,989 | $395 | $46,227 | $65,611 |
| demand_shock | safety_stock | 77.9% | 16.7% | $19,735 | $533 | $35,049 | $55,316 |
| demand_shock | dynamic | 83.2% | 11.8% | $16,456 | $1,204 | $30,253 | $47,913 |
| supply_disruption | reorder_point | 66.9% | 31.4% | $18,704 | $310 | $48,538 | $67,552 |
| supply_disruption | safety_stock | 71.1% | 24.4% | $20,106 | $420 | $40,604 | $61,131 |
| supply_disruption | dynamic | 77.6% | 18.5% | $17,796 | $573 | $35,639 | $54,007 |

## 4. V4 — Real operational validation: not performed

Not validated in v0.1 and not claimed:

- that the synthetic operational data (warehouses, suppliers, lead times, costs, initial inventory, purchase orders) resembles any real company's operations;
- that synthetic demand reproduces real demand beyond the descriptive statistics in §3.2 (known gap: runs of zero-sales days in the reference data are not reproduced);
- that any replenishment strategy is economically or operationally better in reality — strategy results compare strategies under identical simulated conditions only;
- that M5 sales equal demand: M5 records observed sales and has no inventory data; zero observed sales may reflect true zero demand, stockouts or other demand censoring, which the reference cannot distinguish. M5 serves as a reference demand/sales environment, not as true demand and not as warehouse operational data.

Needed for V4: real SKU-level demand with stockout flags, inventory snapshots, purchase-order history with actual lead times, cost data, and a backtest or pilot against current practice ([future-roadmap.md §2.1](future-roadmap.md)).
