# Requirements — v0.1

Status: **Approved at Gate 0 (2026-09-27), v0.1 baseline** · Language: English (authoritative) · 中文: [zh/requirements.md](zh/requirements.md)

## 1. Background

In industrial AI projects the main bottleneck is usually not model capability but **data acquisition
cost, data scarcity and trustworthiness of results**. This project makes **synthetic data** a core
framework capability and combines it with simulation and scenario analysis to provide reusable
foundations for multiple industrial scenarios.

## 2. Objective

Build a reusable **Industrial AI Application Framework Prototype** that provides:

```
Data → Synthetic Data → Prediction / Simulation → Scenario / Strategy → Application → Decision Support
```

and prove it with one concrete validation scenario:

> **Warehouse / Inventory — Inventory Demand Forecasting & Replenishment Simulation**
> Starting from historical sales (demand) data, generate controllable synthetic demand and operational data,
> and compare how different replenishment strategies perform under different demand/supply scenarios.

The warehouse scenario is a **plugin / validation case**, not the framework.

## 3. Users

| Role | Type | Needs |
|---|---|---|
| Operations Manager | Primary (demo UI) | Current operational state, inventory level, stockouts, replenishment, demand changes, what-if scenarios, strategy outcomes |
| Management | Primary (demo UI) | Overall KPIs, scenario comparison, cost/service trade-off, trends, decision support |
| Data scientist / engineer / developer | Secondary (framework users) | Extend with new generators, models, strategies, scenarios through documented APIs |

The UI emphasises operational state, KPIs, scenarios, what-if analysis and strategy comparison, **not**
model internals.

## 4. Functional requirements

IDs are referenced from tests and the task backlog. Priority: **P0** must, **P1** should, **P2** future.

### Foundation (FR-F)

| ID | Requirement | Priority |
|---|---|---|
| FR-F1 | Register datasets in a catalog with id, version, schema, metadata, source and provenance | P0 |
| FR-F2 | Validate a dataset against its schema (types, required fields, ranges, keys) | P0 |
| FR-F3 | Ingest CSV/Parquet tabular data through loaders | P0 |
| FR-F4 | Convert M5 raw files to the canonical data model via a dedicated adapter | P0 |
| FR-F5 | Preview a dataset (first N rows, row count, schema summary) | P0 |
| FR-F6 | Record external-source attribution (source, URL, version, download date, license notes) | P0 |
| FR-F7 | Knowledge / multimodal representations | P2 (interface reserved only) |

### Synthetic data (FR-S)

| ID | Requirement | Priority |
|---|---|---|
| FR-S1 | One common generator interface: `generate(schema, constraints, scenario, seed, size, parameters) → SyntheticDataset` | P0 |
| FR-S2 | Generator registry; discovery by id + version; new generators register without core changes | P0 |
| FR-S3 | Rule-based generator (inventory, supplier, lead time, operational parameters) | P0 |
| FR-S4 | Statistical generator (distributions, sampling, correlations) | P0 |
| FR-S5 | Time-series generator (trend, seasonality, noise, shocks) | P0 |
| FR-S6 | Constraint validation of generated data | P0 |
| FR-S7 | Full provenance for every generated dataset | P0 |
| FR-S8 | Deterministic output for identical inputs + seed | P0 |
| FR-S9 | LLM-assisted config proposal (LLM → config → validator → engine) | P1 |
| FR-S10 | GAN / VAE / diffusion / agent-based generators | P2 |

### Simulation / intelligence (FR-M)

| ID | Requirement | Priority |
|---|---|---|
| FR-M1 | Common simulation interface: `run(dataset, scenario, parameters, constraints) → SimulationResult` | P0 |
| FR-M2 | Simulation plugin registry | P0 |
| FR-M3 | Demand forecast plugin: one baseline + one ML model (LightGBM) | P0 |
| FR-M4 | Inventory simulation plugin (daily, single-echelon, lost sales) | P0 |
| FR-M5 | Replenishment strategy plugins: Reorder Point, Safety Stock, Dynamic Replenishment | P0 |
| FR-M6 | Strategy comparison on identical demand and scenario | P0 |
| FR-M7 | Optimization / causal model plugins | P2 (interface compatibility only) |

### Scenario (FR-C)

| ID | Requirement | Priority |
|---|---|---|
| FR-C1 | Scenarios are explicit, versioned, validated configurations (not algorithms) | P0 |
| FR-C2 | Four initial scenarios: Baseline, High Demand, Demand Shock, Supply Disruption | P0 |
| FR-C3 | Any scenario × any compatible model / strategy combination | P0 |
| FR-C4 | User-defined scenario via Scenario Builder (parameters within validated ranges) | P0 |

### Application / UI (FR-A)

| ID | Requirement | Priority |
|---|---|---|
| FR-A1 | Application API (HTTP/JSON) exposing datasets, generators, scenarios, strategies, simulation runs, results | P0 |
| FR-A2 | Scenario workflow orchestration (intent → scenario → data → synthetic → simulation → result) | P0 |
| FR-A3 | UI pages: Overview, Data, Synthetic Data, Scenario Builder, Simulation, Results | P0 |
| FR-A4 | Lightweight BI (filter, group, aggregate, sort, pivot, basic stats) — non-auditable | P1 |
| FR-A5 | Natural-language intent → validated run configuration (limited agent) | P1 |
| FR-A6 | Reporting: exportable run summary | P1 |

## 5. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 Reproducibility | Same source + generator version + parameters + scenario + seed → identical output; tested automatically |
| NFR-2 Traceability | Every dataset and simulation run has provenance and run metadata persisted |
| NFR-3 Extensibility | New generator / model / strategy / scenario plugin added without editing core engine code |
| NFR-4 Separation | Core package never imports scenario code; UI never imports algorithm modules |
| NFR-5 Simplicity | Single-process Python app, SQLite, no distributed infrastructure |
| NFR-6 Performance | Golden Path demo run (subset: ~1 store × 1 category × top-N items, ~5 years daily) completes in < 60 s on a laptop |
| NFR-7 Testability | Unit, integration, scenario and golden-path tests run offline on a committed synthetic fixture |
| NFR-8 Honesty | Outputs are labelled as prototype / synthetic; no Level-4 validation claims |
| NFR-9 Security | No secrets or raw external data in Git; config via environment |

## 6. Demo success criterion

Within **5 minutes** a user can: open the dashboard → select dataset → select generator →
generate synthetic data → select scenario → run simulation with two or more strategies → compare
results → change a what-if parameter and re-run.

## 7. Deliverables (v0.1.0)

1. Industrial AI Framework Prototype (Data → Synthetic → Simulation → Application, end-to-end)
2. Synthetic Data Engine (API, registry, plugins, provenance, reproducibility, validation)
3. Simulation Engine (API, plugin interface, forecast, inventory simulation, strategy evaluation)
4. Warehouse Validation Demo (M5 reference + synthetic operational data, scenarios, what-if)
5. Technical documentation (architecture, APIs, plugins, data model, scenarios, validation results, history, roadmap)
6. **Algorithm & data requirement list**: what algorithms and data are needed to turn each scenario into a
   full production capability (maintained in [future-roadmap.md](future-roadmap.md)).

## 8. Assumptions (confirmed 2026-09-27)

| # | Assumption |
|---|---|
| A1 | Stocking location is **single-echelon**: each M5 store is modelled as its own stocking point replenished from one synthetic supplier. A distribution-centre tier is future work. |
| A2 | Unmet demand is **lost sales** (not back-ordered), matching retail behaviour. |
| A3 | Demo subset: one store × one category × top-N items (default CA_1 × FOODS_3, N = 50); configurable. |
| A4 | Metrics as defined in [data-model.md §6](data-model.md#6-metrics-definitions). |
| A5 | Raw M5 data is never committed; the user extracts a subset locally with a provided script. Tests use a synthetic M5-shaped fixture. |
| A6 | English documentation is authoritative (v1); a Chinese mirror is maintained in `docs/zh/` (v2). |
