# Architecture — v0.1

Status: **Approved at Gate 0 (2026-09-27), v0.1 baseline** · 中文: [zh/architecture.md](zh/architecture.md)
Related ADRs: [ADR-001](adr/ADR-001-api-first.md), [ADR-002](adr/ADR-002-plugin-architecture.md),
[ADR-003](adr/ADR-003-m5-canonical-adapter.md), [ADR-004](adr/ADR-004-scenario-pack-packaging.md), [ADR-005](adr/ADR-005-ui-package.md)

## 1. Layered architecture

```
┌─────────────────────────────────────────────────────┐
│                    UI / UX Layer                    │
│ Dashboard · Data Explorer · Scenario Builder        │
│ Simulation Viewer · KPI / Charts / Tables · Intent  │
└────────────────────────┬────────────────────────────┘
                         │  Application API (HTTP/JSON)
┌────────────────────────▼────────────────────────────┐
│                Application Layer                    │
│ Scenario Workflow · User Intent / Agent [limited]   │
│ Reporting · Decision Support                        │
└────────────────────────┬────────────────────────────┘
                         │  Simulation API
┌────────────────────────▼────────────────────────────┐
│           Simulation / Intelligence Layer           │
│ Forecasting · Simulation · Strategy Evaluation      │
│ Optimization [future] · Causal Modeling [future]    │
└────────────────────────┬────────────────────────────┘
                         │  Dataset API
┌────────────────────────▼────────────────────────────┐
│                 Foundation Layer                    │
│ Data Ingestion · Schema · Catalog · Metadata        │
│ Synthetic Data Engine · Entity Representation       │
│ Knowledge [extension] · Multimodal [extension]      │
└────────────────────────┬────────────────────────────┘
                         │  Synthetic Data API
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
 Rule-based        Statistical        Time-series      (+ user plugins)

──────────────── Cross-cutting infrastructure ────────────────
Configuration · Logging · Versioning · Plugin Registry
Run / Experiment metadata · Provenance · Validation
```

Scenario plugins sit **beside** the framework and use it only through its public APIs:

```
                 Industrial AI Framework (src/industrial_ai)
                                │  public APIs + plugin registries
            ┌───────────────────┼────────────────────┐
            ▼                   ▼                    ▼
   Warehouse scenario pack   Maintenance [future]   Energy [future]
   (scenarios/warehouse)
```

## 2. Dependency rules (enforced)

| Rule | Enforcement |
|---|---|
| R1 `industrial_ai` never imports any scenario pack | Separate package (ADR-004) + architecture test from Phase 1 |
| R2 Layers depend only downward, as listed in the table below | Architecture test `tests/unit/test_architecture.py` (static import-graph check) |
| R3 UI (templates/static) only talks to the Application API over HTTP | UI contains no Python imports of framework modules; UI routes call API client / HTTP |
| R4 Plugins depend on framework interfaces, never on each other's internals | Code review + tests |
| R5 No module reads raw M5 files except the M5 adapter | Code review |

`core` is shared by all layers and depends on nothing inside the project.

Allowed framework-internal dependencies (R2, enforced by `tests/unit/test_architecture.py`):

| Layer | May import |
|---|---|
| `core` | — |
| `foundation` (incl. datasets, catalog, validation, provenance) | `core` |
| `scenario` | `core`, `foundation` |
| `synthetic` | `core`, `foundation`, `scenario` |
| `simulation` | `core`, `foundation`, `scenario` |
| `application` | `core`, `foundation`, `scenario`, `synthetic`, `simulation` |
| `api` | `core`, `application` |

Any module may import the package root `industrial_ai` (it only holds `__version__`) and third-party
libraries. Changing this table requires updating the test and, if it changes the architecture, an ADR.

## 3. Package / module structure

```
src/industrial_ai/                   # FRAMEWORK CORE — domain-neutral
├── core/          config, logging, errors, ids & versioning, generic Registry[T], plugin discovery
├── foundation/
│   ├── datasets/      Dataset, DatasetSchema, FieldSpec, DatasetRef
│   ├── catalog/       DatasetCatalog (SQLite metadata + artifact storage)
│   ├── ingestion/     tabular loaders (CSV / Parquet), DatasetAdapter protocol
│   ├── transformation/ declarative transforms recorded in provenance
│   ├── provenance/    ProvenanceRecord, lineage helpers
│   ├── entities/      Entity / relationship descriptors (lightweight)
│   └── validation/    schema & constraint validation
├── synthetic/     SyntheticDataGenerator protocol, GeneratorRegistry, SyntheticEngine,
│                  generators/{rule_based, statistical, time_series}, constraints
├── simulation/    SimulationPlugin protocol, SimulationRegistry, SimulationEngine,
│                  forecasting/{baseline, lightgbm}, results, metrics helpers
├── scenario/      ScenarioSpec, ScenarioRegistry (validates against a pack's parameter model),
│                  YAML loading (generic)
├── application/   ScenarioPack protocol, workflow runner, run store, reporting, intent [P1]
└── api/           FastAPI app, routers, request/response models (Application API)

scenarios/warehouse/                 # WAREHOUSE SCENARIO PACK — separate package
└── src/industrial_ai_warehouse/
    ├── adapters/m5/     M5 raw → canonical retail-demand dataset (ADR-003)
    ├── schemas/         canonical demand + synthetic operational schemas
    ├── generators/      generator configurations for inventory, supplier, lead time, PO …
    ├── simulation/      InventorySimulationPlugin, KPI definitions (data-model.md §6)
    ├── strategies/      ReorderPoint, SafetyStock, DynamicReplenishment
    ├── scenarios/       WarehouseScenarioParameters + definitions/{baseline, high_demand,
    │                    demand_shock, supply_disruption}.yaml
    └── pack.py          WarehouseScenarioPack: registers everything with the framework (planned, Phase 12)

ui/                    UI package industrial_ai_ui (Jinja2 + HTMX, SVG charts); calls the Application
                       API over HTTP only, imports no framework module (ADR-005)
scripts/               make_m5_subset.py, make_m5_fixture.py, run_demo.py
```

**Why forecasting is in the core but inventory is in the pack:** time-series forecasting is
domain-neutral (reusable for energy load, sensor signals). Inventory dynamics and replenishment
strategies are warehouse domain logic. The three synthetic generators are generic engines. The
warehouse pack only provides *configurations* (schemas, rules, distributions) for them.

This refines instruction §29 (which listed `simulation/inventory` and `strategies` under the core) to
satisfy the higher-priority rule "warehouse-specific logic must not become core architecture". See ADR-004.

## 4. Key abstractions

| Abstraction | Layer | Purpose | Spec |
|---|---|---|---|
| `Dataset` / `DatasetSchema` | foundation | Tabular data + schema + metadata + provenance | [data-model.md](data-model.md) |
| `DatasetAdapter` | foundation | External format → canonical dataset | [data-model.md](data-model.md), ADR-003 |
| `SyntheticDataGenerator` | synthetic | Pluggable generator | [synthetic-data-api.md](synthetic-data-api.md) |
| `SyntheticDataset` | synthetic | Dataset + generation config + provenance | [synthetic-data-api.md](synthetic-data-api.md) |
| `SimulationPlugin` | simulation | Pluggable forecast / simulation / strategy-evaluation model | [simulation-api.md](simulation-api.md) |
| `ReplenishmentStrategy` | warehouse pack | Pluggable ordering policy used by inventory simulation | [plugin-spec.md](plugin-spec.md) |
| `ScenarioSpec` | scenario | Versioned parameter set (not an algorithm) | [scenario-spec.md](scenario-spec.md) |
| `ScenarioPack` | application | Bundle of schemas, generators, plugins, scenarios, metrics, pipeline for one domain | [plugin-spec.md](plugin-spec.md) |
| `RunRequest` / `RunResult` | application | One reproducible end-to-end run | [application-api.md](application-api.md) |

## 5. Golden Path (runtime flow)

```
User ──► UI ──► Application API  POST /api/runs
                     │
                     ▼
            Workflow runner (application)
                     │  resolves ScenarioPack "warehouse", ScenarioSpec, seed
                     ▼
            Dataset API ── reference dataset (M5 subset → canonical, or fixture)
                     │
          ┌──────────┴───────────┐
          ▼                      ▼
   Reference demand       Synthetic Engine
                           ├─ time_series_v1  → synthetic demand (scenario-adjusted)
                           └─ rule_based_v1 / statistical_v1 → inventory, supplier, lead time, policy
          └──────────┬───────────┘
                     ▼
            Simulation API
             ├─ forecast plugin (seasonal_naive_v1 | lightgbm_v1)
             └─ inventory_simulation_v1 × strategies (reorder_point | safety_stock | dynamic)
                     ▼
            Metrics + ScenarioResult  ──► run store (SQLite + artifacts)
                     ▼
            Application API ──► UI dashboard (KPIs, time series, comparison)
```

Every arrow crossing a layer boundary is a documented interface. Every produced artifact carries
a provenance record linking it back to its inputs, generator/plugin versions, scenario and seed.

## 6. Cross-cutting infrastructure (lightweight)

| Concern | v0.1 implementation |
|---|---|
| Configuration | Pydantic settings from environment / `.env` (`IAI_*`), scenario configs in YAML |
| Logging | stdlib `logging`, structured key=value, run_id in every run log line |
| Versioning | Package semver; every plugin has `id` + `version`; datasets versioned; schema versions |
| Plugin registry | Generic in-process `Registry[T]` keyed by `(id, version)`; scenario packs discovered via Python entry points (`industrial_ai.scenario_packs`) |
| Run / experiment metadata | SQLite (SQLModel): datasets, synthetic generations, runs, results summary |
| Artifact storage | Parquet files under `data/processed/artifacts/` referenced by path + SHA-256 content hash |
| Provenance | `ProvenanceRecord` JSON stored with every dataset / result |
| Validation | Schema + constraint validators in foundation; scenario-behaviour checks in tests |
| Security | API boundary only; no IAM (non-goal) |

## 7. Technology choices

| Choice | Decision |
|---|---|
| Language | Python ≥ 3.11 |
| Environment | uv (`pyproject.toml`, `uv.lock`, workspace for the scenario pack) |
| Data frames | **pandas** (+ NumPy). Polars not used in v0.1: one frame library keeps interfaces simple; LightGBM integrates directly with pandas |
| Columnar storage | Parquet via pyarrow |
| Models / validation | Pydantic v2 |
| Persistence | SQLModel on SQLite |
| API | FastAPI (+ uvicorn) |
| UI | Jinja2 + HTMX, charts via a single vendored JS chart library (decided in Phase 13) |
| ML | LightGBM (Phase 7 only) |
| Dev | pytest, ruff, mypy (strict) |

Dependencies are added only in the phase that needs them (see [task-backlog.md](task-backlog.md)).

## 8. Extension points reserved (not implemented)

| Future capability | Where it plugs in |
|---|---|
| GAN / VAE / diffusion / agent-based / LLM-assisted generators | `SyntheticDataGenerator` + registry |
| Causal models | `SimulationPlugin` with `kind="causal"`; `SimulationResult.prediction` carries effect estimates |
| Optimization | `SimulationPlugin` with `kind="optimization"` or a strategy that consumes a forecast |
| Maintenance / Energy / Production scenarios | New `ScenarioPack` package under `scenarios/` |
| Knowledge / multimodal data | New foundation sub-package behind the Dataset API |
| Natural-language agent | Application `intent` module producing validated `RunRequest`s |
| React / mobile UI | Consumes the same Application API |
