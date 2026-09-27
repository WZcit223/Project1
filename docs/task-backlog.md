# Task Backlog & Phase Plan — v0.1

Status: **Approved at Gate 0 (2026-09-27), v0.1 baseline** · 中文: [zh/task-backlog.md](zh/task-backlog.md)

Each task is small enough for one coding-agent round (1–5 atomic commits). Branching follows [CLAUDE.md](../CLAUDE.md) §7: each major round (phase or significant feature) gets a new branch created from the latest working branch (`phase<N>` with N = the phase number below, e.g. Phase 0 → `phase0`; `feature/<name>` inside a phase); nothing is merged to `main` during work in progress. Do **one task
at a time**, in order, unless dependencies allow otherwise. Every task inherits the rules in
[CLAUDE.md](../CLAUDE.md) (tests, docs, dev log, commit, push) and the Definition of Done.

Task fields: **Objective · Inputs · Outputs / Files · Interfaces · Acceptance · Tests · Non-goals**.
Branch name suggestion in brackets.

## Milestones and gates

| Milestone | Phase | Gate | Depends on | Status |
|---|---|---|---|---|
| M0 Architecture spec | 0 | G0 Architecture documented & approved | — | ✅ approved 2026-09-27 |
| M1 Framework skeleton | 1 | G1 Project starts, tests run | M0 | ✅ approved 2026-09-27 |
| M2 Dataset foundation | 2 | G2 Dataset can be loaded & validated | M1 | ✅ approved 2026-09-27 |
| M3 M5 adapter | 3 | G3 M5 → canonical | M2 | ✅ approved 2026-09-27 |
| M4 Synthetic engine | 4 | G4 Reproducible synthetic data | M2 | ✅ approved 2026-09-27 |
| M5 Synthetic warehouse data | 5 | G5 Operational data generated | M3, M4 | ✅ approved 2026-09-27 |
| M6 Simulation engine | 6 | G6 Simulation engine executes | M2 | ✅ approved 2026-09-27 |
| M7 Forecast plugins | 7 | (part of G6/G7) | M6 | ✅ approved 2026-09-27 |
| M8 Inventory simulation | 8 | G7 Inventory simulation works | M6, M5 | ✅ approved 2026-09-27 |
| M9 Strategies | 9 | G8 Strategies can be compared | M8, M7 | ✅ approved 2026-09-27 (with follow-ups TASK-STR-004) |
| M10 Scenario engine | 10 | (part of G8/G9) | M4, M6 | 🟡 awaiting owner review |
| M11 Golden Path | 11 | G9 Golden Path works | M5–M10 | ⬜ |
| M12 Application API | 12 | G10 API works independently of UI | M11 | ⬜ |
| M13 UI | 13 | G11 UI executes Golden Path | M12 | ⬜ |
| M14 Validation | 14 | G12 Validation passes | M11–M13 | ⬜ |
| M15 Demo | 15 | G13 Demo stable | M14 | ⬜ |
| M16 Docs & release | 16 | G14 v0.1.0 release candidate | M14 | ⬜ |

## Phase 0 — Architecture

### TASK-ARCH-001 — Architecture baseline  [`phase0`] ✅ approved at Gate 0 (2026-09-27)
Objective: uv project, CLAUDE.md, all specs in `docs/`, ADRs, backlog, bilingual mirror. No app logic.
Acceptance: docs internally consistent; `uv run pytest`, `ruff`, `mypy` pass; approved by the project owner (Gate 0).

## Phase 1 — Skeleton

### TASK-CORE-001 — Workspace & package skeleton  [`phase1`] ✅
- Objective: create uv workspace with `scenarios/warehouse` member package `industrial-ai-warehouse`; create empty sub-packages per [architecture.md §3](architecture.md#3-package--module-structure).
- Outputs: `pyproject.toml` (workspace), `scenarios/warehouse/pyproject.toml`, `__init__.py` files, `scripts/`, `ui/` placeholders.
- Acceptance: `uv sync` installs both packages; `import industrial_ai_warehouse` works.
- Tests: import smoke test for both packages.
- Non-goals: any logic.

### TASK-CORE-002 — Architecture enforcement test  [`phase1`] ✅
- Objective: test that `industrial_ai` never imports `industrial_ai_warehouse` and that layers only import downward (R1, R2).
- Interfaces: test walks AST imports of `src/industrial_ai/**`.
- Acceptance: test passes; a deliberately bad import (in a temp file inside the test) fails it.
- Non-goals: third-party import-linter dependency.

### TASK-CORE-003 — Configuration & logging  [`phase1`] ✅
- Objective: `core.config.Settings` (pydantic-settings, `IAI_*` env vars, matches `.env.example`); `core.logging.configure()`.
- Acceptance: settings load from env and defaults; log lines include level/logger/message.
- Tests: env override, invalid value error.
- Non-goals: remote logging, secrets management.

### TASK-CORE-004 — Generic registry & errors  [`phase1`] ✅
- Objective: `core.Registry[T]` keyed by `(id, version)` with latest-version lookup; `core.errors` hierarchy; semver parsing helper.
- Acceptance: register/get/list/contains; duplicates rejected; `get(id)` returns highest semver.
- Tests: unit tests for all behaviours.

### TASK-CORE-005 — FastAPI app & health  [`phase1`] ✅
- Objective: `industrial_ai.api.app:create_app()`, `GET /health` → `{"status":"ok","version":…}`; `scripts/run_api.py` / `uv run` command.
- Acceptance: TestClient returns 200 with correct body.  **Gate 1.**
- Non-goals: other endpoints.

### TASK-CORE-006 — CI workflow  [`phase1`] ✅
- Objective: GitHub Actions: `uv sync --locked`, ruff format check, ruff lint, mypy, pytest on push/PR.
- Acceptance: workflow green on the PR.

## Phase 2 — Dataset foundation

### TASK-DATA-001 — Dataset model  [`phase2`] ✅
- Objective: `FieldSpec`, `DatasetSchema`, `DatasetMetadata`, `Dataset`, `DatasetBundle` per [data-model.md §1](data-model.md#1-framework-dataset-abstraction-domain-neutral-industrial_aifoundation).
- Acceptance: models serialise to/from JSON; schema JSON round-trip.
- Tests: construction, validation errors.

### TASK-DATA-002 — Schema & constraint validation  [`phase2`] ✅
- Objective: `foundation.validation.validate(dataset, constraints) → ValidationReport` (types, nulls, ranges, allowed values, PK uniqueness, FKs within a bundle).
- Tests: one passing and one failing case per constraint type.

### TASK-DATA-003 — Provenance record & content hashing  [`phase2`] ✅
- Objective: `ProvenanceRecord` model; deterministic SHA-256 of a DataFrame (stable column order, dtype normalisation).
- Acceptance: same data → same hash regardless of row index; different data → different hash.

### TASK-DATA-004 — Catalog & artifact store  [`phase2`] ✅
- Objective: SQLite (SQLModel) catalog of datasets + Parquet artifact storage; register, get, list, preview.
- Dependencies added: pandas, pyarrow, sqlmodel.
- Acceptance: register → reload in a new process → identical hash.  **Gate 2.**

### TASK-DATA-005 — Tabular loaders & adapter protocol  [`phase2`] ✅
- Objective: CSV/Parquet loader into a `Dataset` given a schema; `DatasetAdapter` protocol + `AdapterRegistry`.
- Tests: load fixture CSV, schema mismatch error.

## Phase 3 — M5 adapter (warehouse pack)

### TASK-M5-001 — Canonical retail schemas  [`phase3`] ✅
- Objective: `retail.*` schemas per [data-model.md §2](data-model.md#2-canonical-retail-demand-model-warehouse-pack-schema_version-10) in the pack.

### TASK-M5-002 — M5-shaped synthetic fixture  [`phase3`] ✅
- Objective: `scripts/make_m5_fixture.py` writes a small synthetic dataset in raw M5 file layout to `tests/fixtures/m5_like/` (seeded, labelled synthetic).
- Acceptance: re-running produces byte-identical files.

### TASK-M5-003 — M5 adapter  [`phase3`] ✅
- Objective: raw M5 (or subset) → canonical `DatasetBundle` with attribution metadata; wide→long unpivot; weekday re-encoding; events to rows.
- Tests: on fixture: row counts, FK validity, weekday mapping, no negative quantities.  **Gate 3.**

### TASK-M5-004 — Subset extraction script  [`phase3`] ✅
- Objective: `scripts/make_m5_subset.py --stores CA_1 --dept FOODS_3 --top-n 50` for users to run locally on full Kaggle files; writes `data/raw/m5_subset/` + `SOURCE.json`.
- Acceptance: works on the fixture; streams the large sales file without loading everything into memory.
- Non-goals: downloading from Kaggle.

## Phase 4 — Synthetic Data Engine

### TASK-SYN-001 — Generator protocol, SyntheticDataset, registry  [`phase4`] ✅
- Per [synthetic-data-api.md §1–4](synthetic-data-api.md). Acceptance: dummy generator registers and runs; seed recorded; provenance generated.

### TASK-SYN-002 — SyntheticEngine orchestration  [`phase4`] ✅
- Parameter validation → generate → constraint validation → hash → provenance → catalog registration.

### TASK-SYN-003 — Rule-based generator  [`phase4`] ✅
### TASK-SYN-004 — Statistical generator  [`phase4`] ✅
### TASK-SYN-005 — Time-series generator (+ calibration)  [`phase4`] ✅
- Each: contract tests (registration, params, determinism, schema conformance). **Gate 4** after SYN-005.
- Non-goals: GAN/VAE/diffusion/LLM generators.

## Phase 5 — Synthetic warehouse data

### TASK-WH-001 — Operational schemas & generation configs  [`phase5`] ✅
- Objective: `ops.*` schemas and generator configurations; a pack function producing the full hybrid bundle (reference + synthetic ops) from a reference dataset and seed.
- Acceptance: all FKs resolve; Level-2 checks pass; reproducible.  **Gate 5.**

## Phase 6–7 — Simulation engine & forecasting

### TASK-SIM-001 — Simulation protocol, result model, registry, engine  [`phase6`] ✅
- Per [simulation-api.md](simulation-api.md), including `compare()`. **Gate 6** with a dummy plugin.

### TASK-FC-001 — Baseline forecasts (seasonal naive, moving average)  [`phase7`] ✅
### TASK-FC-002 — LightGBM forecast plugin  [`phase7`] ✅
- Dependency added: lightgbm. No look-ahead (test). Accuracy metrics reported. Non-goal: tuning.

## Phase 8–9 — Inventory simulation & strategies (warehouse pack)

### TASK-INV-001 — Inventory simulation plugin  [`phase8`] ✅
- Model per [scenario-spec.md §5](scenario-spec.md#5-inventory-simulation-model); ledger + PO tables.
- Tests: accounting identities; hand-computed 10-day example.  **Gate 7.**

### TASK-INV-002 — Metrics  [`phase8`] ✅
- All metrics in [data-model.md §6](data-model.md#6-metrics-definitions); tests recompute from ledger.

### TASK-STR-001 — Strategy protocol + Reorder Point  [`phase9`] ✅ (protocol delivered early in `phase8`)
### TASK-STR-002 — Safety Stock strategy  [`phase9`] ✅
### TASK-STR-003 — Dynamic replenishment strategy  [`phase9`] ✅
- Acceptance: three strategies compared on identical demand via `engine.compare`.  **Gate 8.**
- Gate 8 acceptance statement (owner, 2026-09-27): *the framework can execute and fairly compare multiple
  interchangeable replenishment strategies under identical controlled simulation conditions, with
  reproducible results and explicit temporal information boundaries.* It is **not** a demonstration that
  any strategy is economically or operationally superior in the real world.

### TASK-STR-004 — Gate 8 follow-ups  [`phase10`] ✅
- Keep `OperationsConfig.order_cost_range` unchanged (the cost structure exposes ordering-cost dominance).
- Separate cost components and volume metrics (ordering / holding / lost-sales cost, total cost, average
  on-hand units and value, purchase orders, units ordered, fill rate, stockout days, unfulfilled demand).
- Label real-subset results as descriptive / smoke-test evidence only.
- Direct no-look-ahead regression test: change demand after a decision date; forecasts, orders and
  decisions before it stay unchanged.
- Define the service-level metric exactly (no ambiguous "service level").
- Document inventory-position semantics per strategy, the intentional adaptation frequencies
  (A historical baseline · B fixed initial buffer · C periodically updated target) and cold start
  (no sales history) as a v0.1 limitation.
- Failure-mode tests: sparse / zero demand, too few forecast errors, invalid forecast values, lead-time
  disruption around review dates.

## Phase 10 — Scenario engine

### TASK-SCN-001 — ScenarioSpec, registry, YAML loading, parameter model  [`phase10`] ✅
### TASK-SCN-002 — Four warehouse scenarios + Level-3 scenario tests  [`phase10`] ✅

## Phase 11 — Golden Path

### TASK-GP-001 — ScenarioPack protocol, pack discovery, workflow runner, run store  [`feature/golden-path`]
### TASK-GP-002 — Golden Path test  [`feature/golden-path`]
- Fixture → canonical → synthetic → forecast → inventory × 3 strategies → 4 scenarios → metrics; reproducible.  **Gate 9.**

## Phase 12 — Application API

### TASK-API-001 — Catalog, generator, scenario, model, strategy endpoints  [`feature/application-api`]
### TASK-API-002 — Runs, results, time series, compare endpoints
- Acceptance: full Golden Path via HTTP only (TestClient).  **Gate 10.**

## Phase 13 — UI

### TASK-UI-001 — Layout, Overview, Data pages  [`feature/ui-dashboard`]
### TASK-UI-002 — Synthetic Data, Scenario Builder pages
### TASK-UI-003 — Simulation, Results pages (+ what-if re-run)
- Acceptance: Golden Path executable from browser; UI code imports no framework module.  **Gate 11.**

## Phase 14–16 — Validation, demo, release

### TASK-VAL-001 — Validation suite & `docs/validation-report.md`  [`feature/validation`]  **Gate 12**
### TASK-DEMO-001 — Demo script, seed data, demo guide (`docs/demo-guide.md`)  **Gate 13**
### TASK-DOC-001 — Technical report, doc refresh (EN + ZH), CHANGELOG, tag `v0.1.0`  **Gate 14**

## P1 (after Golden Path, if time allows)

- TASK-P1-INTENT: NL intent → validated RunRequest (LLM proposal + validator), never executed without confirmation.
- TASK-P1-BI: lightweight BI (pivot, group, filter) on result tables.
- TASK-P1-REPORT: exportable run report (Markdown/HTML).
