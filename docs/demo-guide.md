# Demo Guide — v0.1

Status: **Approved at Gate 13 (2026-09-28); v0.1.0** · 中文: [zh/demo-guide.md](zh/demo-guide.md)

This guide answers one question: *can another person understand the framework, run the Golden Path,
reproduce the result, and understand what has and has not been validated?*

> **What you are looking at.** A **prototype** framework (Data → Synthetic Data → Forecast / Simulation
> → Scenario / Strategy → Application). The warehouse case combines **real reference sales** (a small M5
> subset) with **synthetic operational data**. Results show how strategies compare under identical,
> controlled simulated conditions — they are **not** evidence of real-world performance
> ([validation report](validation-report.md), category V4 not performed).

## 0. What this is

*This prototype demonstrates an **Industrial AI application framework** through an **inventory demand
forecasting and replenishment** scenario, using M5 as reference demand data and synthetic operational
data.* It is not a warehouse product, and it has not been shown to improve any real operation.
**Framework ≠ scenario ≠ real-world validation:** the framework is reusable, the inventory scenario is one
plugin built on it, and real operational validation (V4) has not been performed.

| | Framework (`src/industrial_ai/`) | Scenario pack (`scenarios/warehouse/`) |
|---|---|---|
| Role | Reusable, domain-neutral building blocks | One validation case built only on the framework's public APIs |
| Contains | Datasets + provenance, synthetic generators, forecast plugins, simulation engine, scenario registry, workflow runner, Application API | M5 adapter, retail / operations schemas, inventory simulation, replenishment strategies, four scenarios |
| Rule | Never imports a scenario pack (enforced by tests) | Replaceable: another domain would be another pack |

**Why inventory?** Demand forecasting and replenishment is a well-understood industrial decision
problem with public real demand-like data (M5 sales). It exercises every framework layer — reference
data, synthetic data, forecasting, simulation, strategies, scenarios, results — so it is a good test of
the framework, not the goal of the project.

## 1. Quick start (≈ 5 minutes)

Prerequisites: [uv](https://docs.astral.sh/uv/), Python 3.11+, a clone of this repository (it contains
the small M5 reference subset in `data/reference/m5_subset/`; Kaggle rules apply — do not redistribute).
Run all commands from the repository root; runs are stored in git-ignored `data/processed/`.

```bash
uv sync                                  # locked environment (framework, warehouse pack, UI)
uv run python scripts/demo.py            # scripted Golden Path via the Application API (~20 s)
uv run python scripts/serve.py           # API + UI; open http://127.0.0.1:8000/ui/
```

Optional checks: `uv run pytest` (full test suite, ~2–3 min) and
`uv run python scripts/validation_report.py` (regenerates the validation report, ~3 min).

## 2. Three kinds of data — keep them apart

| Kind | What | Where | Real? |
|---|---|---|---|
| **Reference data** | M5 store-level retail **sales** (Walmart store CA_1, department FOODS_3, top 50 items), calendar, prices | `data/reference/m5_subset/` | Real, but **observed sales**, not demand, and **not warehouse operations** |
| **Synthetic data** | Horizon demand per scenario (calibrated on the reference), warehouses, suppliers, lead times, costs, initial inventory, replenishment settings; purchase orders and inventory come from the simulation | generated per run, stored in the dataset catalog with provenance | Synthetic |
| **Test fixture** | Small M5-shaped **synthetic** dataset used by most tests | `tests/fixtures/m5_like/` | Synthetic |
| *Real operational data* | *Inventory snapshots, PO history, real lead times and costs* | *not available* | *needed for V4 (future)* |

M5 has no inventory information: zero observed sales may be true zero demand, stockouts or other
demand censoring, and the data cannot tell them apart — **zero observed sales ≠ confirmed stockout**.

## 3. Demo flow in the browser (5–10 minutes)

Start `uv run python scripts/serve.py` and open `http://127.0.0.1:8000/ui/`. Every page shows the
"Prototype · Synthetic data" badge.

| Step | Page | Do | Point out |
|---|---|---|---|
| 1 | **Overview** | (empty on first start) | The UI only calls the Application API; the badge marks everything as prototype / synthetic |
| 2 | **Scenario builder** | Look at `high_demand`, `demand_shock`, `supply_disruption`; optionally save a new scenario (e.g. shock ×1.8 for 7 days) | Scenarios are configuration, not code; values validated against the pack's parameter ranges; immutable versions |
| 3 | **Simulation** | Keep the defaults — reference `m5_subset`, scenario `baseline`, forecast `seasonal_naive`, all three strategies, 91 days, seed 20260927 — and **Run** (~6 s) | Three strategies on identical demand and supply draws; the defaults are the documented demo configuration |
| 4 | **Results** (run page) | KPI table and charts | Fill rate vs. costs; ordering / holding / lost-sales cost shown separately |
| 5 | **Simulation** | Same settings, scenario `high_demand` → Run | Same seed and demand stream; only the scenario differs |
| 6 | **Results → Compare** | Tick both runs → Compare selected runs | *If the environment changes, what happens under each strategy?* |
| 7 | **What-if** (baseline run page) | `lead_time_delta` = 5 → Re-run | Same reference, scenario version and seed; one parameter changed |
| 8 | **Data** | Open a run's inventory ledger or the synthetic demand | Source-type badges (reference, synthetic, derived); provenance: producer, seed, scenario, inputs by hash |
| 9 | **Synthetic data** (optional) | Generate the pre-filled example | Any generator can be driven through the API; the result is registered with provenance |

Closing statement: *the same framework ingests reference data, generates controlled synthetic
environments, runs multiple simulations and supports scenario-based operational decision analysis —
validated at the prototype level.*

## 4. Golden Path walkthrough (what happens on "Run")

```
UI form ─► POST /api/runs ─► ApplicationService ─► WorkflowRunner ─► WarehousePack.run
  1 load reference   M5 files → canonical retail bundle (schema checks)        [reference]
  2 operations       rule_based / statistical generators → warehouses, suppliers, lead times, costs [synthetic]
  3 scenario demand  time_series generator calibrated on reference sales, scenario applied        [synthetic]
  4 demand timeline  observed history + synthetic horizon (forecasts never see the future)
  5 forecast         seasonal naive | moving average | LightGBM, rolling origins with 56-day warm-up
  6 simulate         inventory simulation × strategies (reorder point, safety stock, dynamic)
  7 metrics          fill rate, stockout-day rate, ordering / holding / lost-sales / total cost …
  8 persist          run record + every dataset with provenance in the catalog (SQLite + Parquet)
```

Layers: UI → Application API → application → synthetic / simulation engines → plugins → datasets
(architecture.md). The warehouse logic lives in the scenario pack; the framework never imports it.

## 5. Demo scenario and expected outputs

The scripted demo (`scripts/demo.py`) runs `baseline` and `high_demand` (demand ×1.3, stronger
seasonality) and a what-if (`lead_time_delta` +5 days) on the M5 subset, 91-day horizon, seed
20260927, seasonal-naive forecast. With the same commit and seed you get exactly the numbers in the
[validation report §3.2](validation-report.md) Golden Path table (`tests/integration/test_demo.py` checks
that the demo reproduces the report and that this table matches it):

| Scenario | Strategy | Fill rate | Total cost |
|---|---|---|---|
| baseline | reorder_point | 84.7% | $39,248 |
| baseline | safety_stock | 86.2% | $36,995 |
| baseline | dynamic | 93.8% | $29,136 |
| high_demand | reorder_point | 74.3% | $70,030 |
| high_demand | safety_stock | 76.9% | $62,865 |
| high_demand | dynamic | 89.9% | $39,865 |

How to read them: all strategies face identical demand and supply draws, so differences come from the
strategies. Lost-sales cost is valued at full selling price (an upper-bound proxy), so total cost
favours strategies that hold more stock; ordering cost reflects the synthetic 20–60 USD per order.
The UI's default Simulation form uses the same configuration (seasonal naive, 91 days, seed
20260927) and shows the same values; choosing another forecast model (e.g. LightGBM) gives different,
equally reproducible numbers.

## 6. What has and has not been validated (V1–V4)

| Category | Meaning | v0.1 |
|---|---|---|
| **V1** Software / framework correctness | Modules, plugins, interfaces, data structure, metrics behave as specified | ✅ passes |
| **V2** Framework integration / Golden Path | The pipeline works end to end via runner, HTTP API and UI; reproducible; no look-ahead | ✅ passes |
| **V3** Scenario & reference-data validation | Scenarios behave as specified; the framework runs correctly on the real reference subset; comparisons with the reference are descriptive | ✅ passes (comparisons descriptive) |
| **V4** Real operational validation | Results hold for a real warehouse | ⛔ not performed |

Test counts and all numbers are in the generated [validation report](validation-report.md); definitions in
[validation.md](validation.md).
Passing V1–V3 means the framework works as a prototype; it does **not** mean any strategy is better in
reality.

## 7. Reproducing results

- Same inputs → same outputs: reference subset (hash-verified), generator and plugin versions,
  parameters, scenario (id + version + overrides) and **seed**. Run ids differ; metrics and dataset
  content hashes do not.
- Re-run a stored run: post its `pack`, `reference_id`, `scenario_id`, pinned `scenario.version`, `seed`,
  `horizon_days`, `options` and `scenario_overrides` to `POST /api/runs` (application-api.md §1).
- Every dataset's provenance (`GET /api/datasets/{id}`) names its inputs by content hash, the producing
  component and version, parameters, scenario and seed.
- Regenerate the evidence: `uv run python scripts/validation_report.py`.

## 8. Known limitations

- Synthetic operational data is not calibrated on any real company; costs and lead times are plausible
  placeholders (e.g. ordering cost 20–60 USD per order dominates inventory cost).
- Synthetic demand has far fewer zero-sales days than the M5 reference, and its mean is higher than the
  reference mean (close on days with sales) — figures in validation report §3.2. Zero observed sales
  in M5 cannot be attributed to stockouts or true zero demand. Zero-run modelling is on the roadmap.
- Single echelon, lost sales, daily; textbook strategies without optimisation; strategies differ in
  adaptation frequency by design (plugin-spec §4).
- Cold start: items without sales history are never replenished.
- Runs are synchronous; single-user demo; no authentication; English UI; chart legends may overlap
  (cosmetic).
- `demand_source = reference` (replaying reference demand) is not implemented.
