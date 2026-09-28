# Changelog

All notable changes to this project. Format based on [Keep a Changelog](https://keepachangelog.com/);
versions follow [Semantic Versioning](https://semver.org/). Detailed round-by-round history:
[docs/development-log.md](docs/development-log.md).

## [0.1.0] — unreleased (release candidate, pending owner approval)

First prototype release of the **Industrial AI Application Framework**, demonstrated through an
Inventory Demand Forecasting & Replenishment scenario (M5 reference sales + synthetic operational
data). **Prototype level only:** real operational validation (V4) has not been performed. See
[docs/technical-report.md](docs/technical-report.md).

### Added — framework (`src/industrial_ai/`)
- **core:** settings from environment / `.env` (`IAI_*`), structured logging, error hierarchy,
  semantic versioning helpers, generic plugin `Registry[T]` keyed by id + version (Phase 1).
- **foundation:** `Dataset` / `DatasetSchema` with invariant checks, deterministic SHA-256 content
  hashing, `ProvenanceRecord`, schema and constraint validation, CSV / Parquet ingestion,
  `DatasetAdapter` protocol, `DatasetCatalog` (SQLite metadata + Parquet artifacts) (Phase 2).
- **synthetic:** `SyntheticDataGenerator` protocol, registry and engine (parameter validation →
  generate → constraint validation → hash → provenance → catalog); generators `rule_based`,
  `statistical` (with rank correlation) and `time_series` (level, seasonality, events, noise, scenario
  effects; calibrated on reference history) (Phase 4).
- **simulation:** `SimulationPlugin` protocol, registry and engine with result datasets and metrics;
  forecasting plugins `seasonal_naive`, `moving_average`, `lightgbm` with rolling origins and no
  look-ahead (Phases 6–7).
- **scenario:** `ScenarioSpec`, `ScenarioRegistry` validating against a pack's parameter model, YAML
  loading; immutable versions (Phase 10).
- **application:** `ScenarioPack` protocol with entry-point discovery, `WorkflowRunner`, `RunStore`
  (content-identical datasets reused, conflicts refused), `ApplicationService`, user-defined scenarios
  (Phases 11–12).
- **api:** FastAPI Application API — scenario packs, references, datasets, synthetic generation,
  scenarios, models, strategies, runs, results, time series, cross-run comparison; uniform error shape;
  server paths never exposed (Phase 12).

### Added — inventory scenario pack (`scenarios/warehouse/`)
- M5 adapter → canonical retail bundle (region, store, category, department, product, calendar,
  events, SNAP, sales, prices) with source metadata (Phase 3).
- Synthetic operational data: warehouses, suppliers, lead times, costs, initial inventory,
  replenishment settings; hybrid bundle validation (Phase 5).
- Inventory simulation plugin (single echelon, daily, lost sales) and KPIs: fill rate, stockout days
  and rate, on-hand units / value, turnover, orders, ordering / holding / lost-sales / total cost
  (Phase 8).
- Replenishment strategies `reorder_point`, `safety_stock`, `dynamic` compared under common random
  numbers (Phase 9, Gate 8 follow-ups).
- Scenarios `baseline`, `high_demand`, `demand_shock`, `supply_disruption` (Phase 10).
- `WarehouseScenarioPack` Golden Path: reference → synthetic → forecast → simulation × strategies →
  metrics, persisted with provenance (Phase 11).

### Added — UI (`ui/`, ADR-005)
- Server-rendered Jinja2 + HTMX UI (vendored htmx 2.0.4) with SVG charts: overview, data catalog with
  provenance, synthetic data, scenario builder, simulation, results, compare, what-if. Calls only the
  Application API; prototype / synthetic labels on every page (Phase 13).

### Added — validation, demo and documentation
- Validation categories V1–V4 and `scripts/validation_report.py` → `docs/validation-report.md`,
  including the coverage check V1 + V2 + V3 = all tests (Phase 14).
- `scripts/demo.py` (scripted Golden Path via the Application API), `scripts/serve.py`,
  `docs/demo-guide.md` (Phase 15).
- Specifications, ADR-001 … ADR-005, Chinese mirror in `docs/zh/`, development log, roadmap;
  `docs/technical-report.md`, this changelog and `docs/release-checklist.md` (Phase 16).

### Data
- Committed, owner-approved M5 subset `data/reference/m5_subset/` (CA_1 / FOODS_3 / top 50; Kaggle
  competition rules, do not redistribute) and a synthetic M5-shaped test fixture.

### Known limitations
See [docs/technical-report.md §6](docs/technical-report.md#6-known-limitations). P2 polish items
TASK-P2-LEGEND and TASK-P2-GENFORMS remain open by decision.
