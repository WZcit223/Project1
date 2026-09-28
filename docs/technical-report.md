# Technical Report — v0.1.0

Status: **v0.1.0 release candidate (Phase 16)** · 中文: [zh/technical-report.md](zh/technical-report.md)

For a technical reviewer with 10–15 minutes. Each section answers one question and links to the spec
that holds the detail.

> **Claim.** *The framework validates synthetic data generation and scenario execution at the
> prototype level.* Real operational validation (V4) has **not** been performed. Nothing in this
> repository shows that any strategy, forecast or synthetic dataset is correct for a real warehouse.

## 1. What is this?

An **Industrial AI Application Framework prototype**: reusable building blocks for the chain
*data → synthetic data → forecast / simulation → scenario / strategy → application → decision support*.

It is demonstrated through **one** scenario, *Inventory Demand Forecasting & Replenishment*, using M5
(store-level Walmart retail sales) as **reference demand data** and **synthetic operational data** for
everything else. It is not a warehouse product.

| | What it is | Where |
|---|---|---|
| **Framework** | Domain-neutral datasets, provenance, synthetic generators, forecasting, simulation engine, scenario registry, workflow runner, Application API | `src/industrial_ai/` |
| **Scenario** | One inventory case built on the framework's public APIs | `scenarios/warehouse/` (plugin package) |
| **UI** | Server-rendered demo UI that only calls the Application API | `ui/` |
| **Real-world validation** | Evidence that results hold for a real operation | **Not performed (V4)** |

## 2. What architecture does it demonstrate?

**Layers** ([architecture.md](architecture.md)): each depends only downward; enforced by an import-graph
test (`tests/unit/test_architecture.py`).

```
Application      workflow runner, run store, ScenarioPack protocol, Application API (FastAPI)
      ▲
Simulation /     SimulationEngine + plugins: forecasting (seasonal naive, moving average, LightGBM);
Intelligence     inventory simulation and strategies come from the scenario pack
      ▲
Synthetic Data   SyntheticEngine + generators: rule_based, statistical, time_series
      ▲
Foundation       Dataset / schema / catalog / validation / provenance / ingestion
      ▲
core             config, logging, errors, versioning, generic plugin Registry
```

**Golden Path** (one `POST /api/runs`, [demo-guide.md §4](demo-guide.md)):

```
Reference data (M5 subset) → canonical dataset (schema-checked) → synthetic operations + scenario demand
→ forecast (rolling origins, no look-ahead) → inventory simulation × strategies → metrics
→ scenario comparison → persisted result with provenance
```

Design rules that the code enforces rather than just states:

- **Framework first** — `industrial_ai` never imports a scenario pack (test R1); packs are discovered
  through the entry point `industrial_ai.scenario_packs` ([ADR-004](adr/ADR-004-scenario-pack-packaging.md)).
- **Scenario ≠ algorithm** — scenarios are versioned, immutable parameter sets (YAML or user-defined),
  validated against the pack's parameter model; any scenario runs with any strategy and forecast model
  ([scenario-spec.md](scenario-spec.md)).
- **API first / UI boundary** — UI → Application API → application → engines → plugins → datasets; the
  UI package imports no framework module (AST test, [ADR-005](adr/ADR-005-ui-package.md)).
- **Plugins** by `id` + `version` in registries; adding one needs no engine change
  ([plugin-spec.md](plugin-spec.md)).
- **Reproducibility and provenance** — same reference + component versions + parameters + scenario
  (id, version, overrides) + seed → same metrics and dataset content hashes; every dataset records its
  inputs by content hash, producer, parameters, scenario and seed.

## 3. What is framework-level and what is scenario-level?

| Concern | Framework (reusable) | Inventory scenario pack |
|---|---|---|
| Data | `Dataset`, `DatasetSchema`, `DatasetCatalog`, validation, provenance, CSV/Parquet ingestion, `DatasetAdapter` protocol | M5 adapter, canonical retail schemas, operations schemas |
| Synthetic data | `SyntheticDataGenerator` protocol, registry, engine, generators `rule_based`, `statistical`, `time_series` | Generator *configurations*: warehouses, suppliers, lead times, costs, initial inventory, replenishment settings; demand calibration |
| Simulation | `SimulationPlugin` protocol, registry, engine; forecasting plugins (domain-neutral time series) | `inventory_simulation` plugin, KPI definitions, `ReplenishmentStrategy` + `reorder_point`, `safety_stock`, `dynamic` |
| Scenarios | `ScenarioSpec`, `ScenarioRegistry`, YAML loading | `WarehouseScenarioParameters`; `baseline`, `high_demand`, `demand_shock`, `supply_disruption` |
| Application | `ScenarioPack` protocol, `WorkflowRunner`, `RunStore`, `ApplicationService`, Application API | `WarehouseScenarioPack.run` (the pipeline for this domain) |
| UI | — (separate package, talks HTTP) | Display labels and the demo defaults (scenario `baseline`, model `seasonal_naive`) only |

A second domain (e.g. maintenance) would be a new pack under `scenarios/`; the framework would not
change. This has **not** been demonstrated with a second pack in v0.1.

## 4. What was actually tested?

From [validation-report.md](validation-report.md) (generated by `scripts/validation_report.py` at commit
`47221e4`, version 0.1.0; the script also checks that V1 + V2 + V3 covers every collected test exactly
once — 379 of 379):

| Category | Question | v0.1 evidence | Result |
|---|---|---|---|
| **V1** Software / framework correctness | Do modules, plugins, interfaces and metrics behave as specified? | 314 unit and contract tests: registries, datasets, hashing, provenance, validation, generators (structure, constraints, reproducibility), plugins, metric definitions, failure modes, architecture import rules | ✅ |
| **V2** Integration / Golden Path | Does the whole chain work end to end, through runner, HTTP API and browser UI? | 51 tests on the synthetic M5-shaped fixture: Golden Path, API contract and errors, UI flows, reproducibility, no look-ahead, fair comparison (common random numbers) | ✅ |
| **V3** Scenario & reference-data validation | Do scenarios behave as specified; does the framework run correctly on real reference data? | 14 tests (scenario behaviour; runs on the committed M5 subset) + 279 data checks; calibration comparison, forecast backtest and Golden Path on the subset — **descriptive** | ✅ prototype level |
| **V4** Real operational validation | Do results hold for a real warehouse? | None | ⛔ **Not performed** |

Selected V3 figures (descriptive, not pass/fail equivalence):

| | Value |
|---|---|
| Synthetic vs reference mean demand per series-day | 14.63 vs 18.24 (+25%); on days with sales 17.48 vs 18.75 (reference vs synthetic) |
| Zero series-days | 16.3% (reference) vs 2.7% (synthetic) |
| Item-level mean correlation | 0.905 |
| Forecast backtest WAPE (seasonal naive / moving average / LightGBM) | 0.443 / 0.459 / 0.413 |
| Golden Path on the subset, baseline, fill rate (reorder point / safety stock / dynamic) | 84.7% / 86.2% / 93.8% — reproduced exactly by `scripts/demo.py` and the default UI run |

## 5. What has NOT been demonstrated?

- **V4 real operational validation** — no real inventory, purchase-order, lead-time or cost data; no pilot.
- That synthetic operational data resembles any real company.
- That any strategy is better in reality. Strategy comparisons hold only under identical, controlled
  **simulated** conditions.
- That forecasts are competitive (the models are baselines plus one practical ML model, not an M5
  solution).
- A second scenario pack, multi-user operation, security, production deployment.

Synthetic and reference-data validation (V1–V3) is not production validation.

## 6. Known limitations

**Data**
- M5 is store-level **observed retail sales** — reference data, not warehouse inventory observations; it
  has no on-hand or stockout information.
- **Zero observed sales ≠ confirmed stockout**: zeros may be true zero demand, stockouts or other
  censoring, and the data cannot tell them apart. Observed sales are a proxy for demand.
- Only the owner-approved subset `data/reference/m5_subset/` (CA_1 / FOODS_3 / top 50) is used;
  Kaggle rules apply, do not redistribute.

**Synthetic demand**
- Fewer zero days than the reference and a higher overall mean (close on days with sales); zero-run /
  intermittent-demand modelling is on the roadmap.
- Operational data (costs, lead times, suppliers) are plausible placeholders, not calibrated on a
  company; ordering cost (20–60 USD per order) dominates inventory cost.

**Inventory simulation**
- Single echelon (one stocking point per item and store), one external synthetic supplier per item,
  daily steps, lost sales (no backorders or substitution).
- Textbook strategies (reorder point, safety stock, periodic order-up-to) without optimisation; they
  adapt at different frequencies by design ([plugin-spec.md §4](plugin-spec.md)).
- Lost-sales cost is valued at full selling price (an upper-bound proxy), which favours high-stock
  strategies in total cost.
- Cold start: items without sales history are never replenished.
- `demand_source = reference` (replaying reference demand) is not implemented.

**Application / UI**
- Synchronous runs, single user, SQLite, no authentication, English UI.
- P2 polish: chart legends can overlap lines (TASK-P2-LEGEND); synthetic generation takes a JSON
  request rather than a form (TASK-P2-GENFORMS).

## 7. What comes next?

**v0.1 scope ends here.** v0.1.0 is a reproducible, clearly scoped prototype; it will not gain further
capabilities.

Candidates for later versions ([future-roadmap.md](future-roadmap.md)), none started:

| Horizon | Items |
|---|---|
| Next (P1) | Limited NL intent → validated run request; lightweight BI; run report export; generator forms |
| Later (P2) | Intermittent-demand option; cold-start handling; optimisation and causal plugins; async runs; fidelity metrics against real data |
| Requires a partner | **V4**: real inventory snapshots, PO history, real lead times and costs, backtest and pilot |
| Long-term (P3) | Further scenario packs (maintenance, energy), knowledge / multimodal layers, enterprise deployment |

## Appendix — reproduce in five commands

```bash
uv sync
uv run python scripts/demo.py                 # Golden Path via the Application API (~20 s)
uv run python scripts/serve.py                # UI at http://127.0.0.1:8000/ui/ — default form = demo configuration
uv run pytest                                 # 379 tests
uv run python scripts/validation_report.py    # regenerates docs/validation-report.md
```

Demo configuration: reference `m5_subset`, scenario `baseline` 1.0.0 (and `high_demand`), forecast
`seasonal_naive`, seed 20260927, 91-day horizon.
