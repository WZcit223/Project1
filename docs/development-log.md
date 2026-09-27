# Development Log

Human-readable record of every meaningful development round (newest first).
Fields: Date · Branch · Objective · Changes · Files / Modules · Tests · Commit · Known Issues · Next.

---

## 2026-09-27 — Phase 4: Synthetic Data Engine (TASK-SYN-001 … 005)

### Branch
`phase4` — based on `phase3` @ `93b8062`

### Objective
Gate 4: synthetic data can be generated reproducibly, with full provenance and validation, from a
pluggable engine with exactly three generators.

### Changes
- **SYN-001** `industrial_ai.scenario.ScenarioSpec` (minimal, generic; registry/YAML in Phase 10);
  `synthetic.base`: `SyntheticDataGenerator` protocol, `GenerationSize`, `GeneratedData`,
  `GenerationConfig`, `SyntheticDataset`; generator registry + `describe()`.
- **SYN-002** `SyntheticEngine` + `GenerationRequest`: parameter validation, reference from argument or
  catalog, provenance (inputs pinned by hash, component, parameters, scenario, seed, steps, warnings),
  schema/constraint validation (`ConstraintViolationError` on failure), optional catalog registration.
- **SYN-003** `rule_based` 1.0.0: whitelisted rules (constant, sequence, choice, uniform, linear,
  lookup, reference_column).
- **SYN-004** `statistical` 1.0.0: seven distributions, Iman–Conover rank correlation (no SciPy),
  explicit clipping recorded in provenance.
- **SYN-005** `time_series` 1.0.0: per-series calibration (leading zeros excluded), weekly/monthly
  seasonality, events, negative binomial / Poisson noise, generic scenario effects with
  `scenario_mapping`; one seed stream per series.
- Refactor: generators report `applied_scenario_parameters`; the engine warns about the rest.
- Gate 4 integration test: fixture → adapter → catalog → three generators → registered datasets;
  two independent runs give identical hashes.
- synthetic-data-api.md §1, 2, 4, 6 describe the implemented interfaces (EN + ZH).

### Decisions / assumptions
- Generators return `GeneratedData`; only the engine writes provenance and validation (plugins cannot
  fabricate them). Spec sketch previously had `generate()` return a `SyntheticDataset`.
- Unused scenario parameters are warnings (in the result and in provenance), never silent.
- Time-series scenario effects have generic names; the warehouse pack will map
  `demand_multiplier → level_multiplier` (keeps the core domain-neutral).
- v1 time series: no trend term, no calibrated event uplift (explicit event dates only).
- Rank correlation via Iman–Conover instead of a Gaussian copula with inverse CDFs (avoids SciPy;
  marginals exact, correlation approximate).

### Local check on the real M5 subset (descriptive, not committed)
Calibrated on 50 CA_1 / FOODS_3 series, 182-day horizon: weekday profile real
[0.94, 0.84, 0.82, 0.81, 0.99, 1.25, 1.35] vs synthetic [0.94, 0.85, 0.83, 0.80, 0.98, 1.24, 1.35];
High Demand / baseline total = 1.33 (demand ×1.3 with seasonality ×1.2); mean per item-day 17.4
(synthetic horizon) vs 15.8 (real, last 730 days); share of zero days 3.8 % vs 15.4 % — runs of zeros
in the real data (likely stockouts) are not reproduced. Generation takes about 0.3 s. No
statistical-equivalence claim (Level 4 is out of scope).

### Tests / checks
ruff, mypy strict, pytest: 213 passed locally (incl. `m5_local` on the real subset); in CI the `m5_local` test is skipped.

### Commits
964f511 protocol/registry/engine, 42f8b8a rule_based, 296a919 statistical, c0dee66 applied
scenario parameters, ddea970 time_series, 9e58448 Gate 4 test, + docs commits.

### Known issues
- Zero-run (stockout / intermittency) structure of real demand not modelled; candidate for a later
  generator version or intermittent-demand option (recorded in the roadmap).

### Next
Owner review of Gate 4 → Phase 5 (synthetic warehouse operational data) on `phase5` from `phase4`.

---

## 2026-09-27 — Real M5 subset check · Gate 3 approved

### Branch
`phase3`

### Objective
Confirm the adapter on real M5 data supplied by the owner, and record Gate 3 approval.

### Changes
- Owner ran `scripts/m5_subset_standalone.py` (added in e54be5b: same output as the project script,
  needs only Python ≥ 3.10 + pandas) on the Kaggle files and uploaded the output; it was placed in
  git-ignored `data/raw/m5_subset/` (**not committed**).
- Gate 3 and the four Phase 3 decisions approved by the owner; M3 ✅ in the backlog (EN + ZH).

### Real-data check (`uv run pytest -m m5_local` + profile)
- `SOURCE.json`: `m5_subset_ca_1_foods_3_top50`, reference data, downloaded 2026-09-20, filters
  CA_1 / FOODS_3 / top 50; `calendar.csv` SHA-256 equals the recorded hash of the original file.
- Conversion: all 10 canonical tables; `validate_bundle`: 85 checks, 0 failed, 0 skipped.
- Sales: 50 items × 1,941 days (2011-01-29 … 2016-05-22) = 97,050 rows; 1,580,183 units; no
  negative or missing values. Per-item daily mean 7.8 – 66.4 (median 13.8); share of zero-sale days
  median 20.5 %, max 53.1 %; 11 items have their first sale after 2011-03-01 (late launch).
- Prices: 13,227 weekly rows, 0.20 – 4.98 USD. Calendar 1,969 days (to 2016-06-19), 167 events.

### Known issues / notes for later phases
- Leading zeros before an item's first sale (not yet on sale) must not be treated as zero demand when
  calibrating synthetic demand (Phase 4/5).
- Observed sales remain censored by stockouts (documented limitation).

### Next
Phase 4 (Synthetic Data Engine) on branch `phase4` created from `phase3`.

---

## 2026-09-27 — Phase 3: M5 adapter (TASK-M5-001 … 004)

### Branch
`phase3` — based on `phase2` @ `ec945b5`

### Objective
Gate 3: M5 can be converted to the canonical schema — without real M5 data in the repository.

### Changes
- **M5-001** `industrial_ai_warehouse.schemas.retail`: ten canonical retail schemas (1.0.0) with
  primary/foreign keys, time index and entity keys.
- **M5-002** `adapters.m5.source` (`M5Source` = `SOURCE.json`, `SubsetFilters`, M5 constants) and
  `adapters.m5.fixture` + `scripts/make_m5_fixture.py`: synthetic, M5-layout fixture in
  `tests/fixtures/m5_like/` (2 stores × 2 departments × 6 items × 1,100 days), byte-identical on
  regeneration, labelled `source_type=fixture`.
- **M5-003** `adapters.m5.M5Adapter` (`m5` 1.0.0): unpivot, ISO weekday (cross-checked), event and
  SNAP rows, deterministic sorting, attribution + per-table provenance; bundle validates with no
  failed or skipped checks.
- **M5-004** `adapters.m5.subset` + `scripts/make_m5_subset.py`: streaming subset extraction with
  verbatim values and `SOURCE.json`; optional `pytest -m m5_local` check of `data/raw/m5_subset/`.
- mypy also covers `scripts/`; pytest marker `m5_local` registered.

### Decisions / assumptions
- SNAP flags modelled as long table `retail.calendar_snap` instead of per-state calendar columns
  (keeps the canonical calendar region-agnostic); data-model.md updated (EN + ZH).
- Without `SOURCE.json`, a folder is treated as original Kaggle files (`reference`, id `m5`,
  download date unknown — recorded as such, never invented).
- Canonical tables take `created_at` from `SOURCE.json`, so conversion is fully deterministic.
- Prices are kept only for product/store series present in the sales file.
- The adapter targets subsets; the full 30,490-series unpivot is not supported in v0.1 (memory).
- Subset top-N ranks items by total sales across the selected stores; ties broken by item id.

### Files / Modules
`scenarios/warehouse/src/industrial_ai_warehouse/{schemas,adapters}/`, `scripts/make_m5_fixture.py`,
`scripts/make_m5_subset.py`, `tests/fixtures/m5_like/`, `tests/unit/warehouse/`,
`tests/integration/test_m5_local.py`, `docs/data-model.md` §2, §5 (+ ZH), `README.md`, `pyproject.toml`.

### Tests / checks
ruff format + lint, mypy strict (src, pack, tests, scripts), pytest: 167 passed, 1 skipped
(`m5_local`, no local subset). CI on `phase3`: see Actions.

### Commits
574bd29 retail schemas, b2664c9 fixture + SOURCE.json, 4e6282d M5 adapter, 7ece2c0 subset script,
+ docs(log) for this entry.

### Known issues
- Not yet run on the real M5 subset: needs the owner to run `make_m5_subset.py` and upload / place
  the output in `data/raw/m5_subset/`.
- M5 sales are observed sales (censored by stockouts); documented, not corrected.

### Next
Owner review of Gate 3 (and real-subset upload when convenient) → Phase 4 (Synthetic Data Engine)
on branch `phase4` from `phase3`.

---

## 2026-09-27 — Gate 2 approved

### Branch
`phase2`

### Changes
- Owner approved Gate 2 and the five Phase 2 decisions (hash semantics, provenance `component`,
  `skipped` checks, strict CSV conversion, free-form dataset versions). M2 ✅ in the backlog (EN + ZH).

### Next
Phase 3 (M5 adapter) on branch `phase3` created from `phase2`.

---

## 2026-09-27 — Phase 2: Dataset foundation (TASK-DATA-001 … 005)

### Branch
`phase2` — based on `phase1` @ `82129d9`

### Objective
Gate 2: a dataset can be loaded, validated, registered and reloaded unchanged.

### Changes
- **DATA-003** (done first; the dataset model embeds it) `foundation.provenance`: deterministic
  `content_hash()` (index- and column-order-independent, logical dtype families, row order kept,
  stable across Parquet), `file_hash()`, immutable `ProvenanceRecord` / `Lineage`.
- **DATA-001** `foundation.datasets`: `FieldSpec`, `DatasetSchema`, `SourceInfo`, `DatasetMetadata`,
  `Dataset` (invariants re-checked on construction), `build_dataset()`, `DatasetBundle`.
- **DATA-002** `foundation.validation`: declarative constraints (range, not_null, unique, integer,
  foreign_key, relation), `validate_dataset()` / `validate_bundle()`, reports with
  passed / failed / skipped and offending-row counts.
- **DATA-004** `foundation.catalog.DatasetCatalog`: SQLite (SQLModel) + Parquet; hash verified on
  write and on read; list, preview, bundles.
- **DATA-005** `foundation.ingestion`: `load_table()` for CSV/Parquet with strict type conversion,
  `DatasetAdapter` protocol and adapter registry.
- mypy now also type-checks `tests/` (strict).
- Integration test: file → load → validate → register → fresh catalog → reload, hash unchanged.

### Dependencies added
Runtime: pandas 3, pyarrow, sqlmodel (with numpy, sqlalchemy). Dev: pandas-stubs.

### Decisions / assumptions
- Content hash keeps row order (generators/adapters produce deterministic order) but ignores index,
  column order and physical dtype width.
- Provenance field `component` (not `generator`), since loaders and adapters also produce datasets;
  synthetic-data-api.md example updated (EN + ZH).
- Metadata `entities` made precise as `entity_counts` (distinct values per entity key).
- Validation reports checks that cannot run as `skipped` (visible, not counted as passed).
- Dataset versions are free-form strings; "latest" = most recently registered. Plugin and schema
  versions stay semver.
- Loader rejects unconvertible CSV values instead of coercing them to missing.
- Phase 2 tasks were implemented directly on `phase2` (each a separate commit).

### Files / Modules
`src/industrial_ai/foundation/{provenance,datasets,validation,catalog,ingestion}/`,
`src/industrial_ai/core/errors.py`, `tests/unit/foundation/`, `tests/integration/`,
`docs/data-model.md` §1.3–1.7, `docs/synthetic-data-api.md` §5 (+ ZH), `pyproject.toml`, `uv.lock`.

### Tests / checks
ruff format + lint, mypy strict (src + tests), pytest: 140 passed, including a cross-process
reload test and the Gate 2 integration test. CI green on `phase2`.

### Commits
baa1a7a provenance/hashing, ecb1185 datasets, 8aa8cd0 mypy tests, dce5ee7 validation,
3217f9a catalog, 6ecfb2c ingestion, 4ea4f57 integration test, + docs(log) for this entry.

### Known issues
- `foundation.transformation` and `foundation.entities` are not built yet (not needed until later phases).
- Observed-sales-vs-true-demand limitation of M5 remains documented, not corrected (data-model.md §2).

### Next
Owner review of Gate 2 → Phase 3 (M5 adapter: canonical retail schemas, synthetic M5-shaped
fixture, adapter, subset-extraction script) on branch `phase3` from `phase2`.

---

## 2026-09-27 — Gate 1 approved

### Branch
`phase1`

### Objective
Record the owner's Gate 1 approval and review decisions.

### Changes
- Gate 1 (project starts, tests run) approved; M1 ✅ in the backlog (EN + ZH).
- Phase 1 decisions accepted: tasks on `phase1` directly, explicit layer dependency table,
  `api` limited to `core` + `application`.
- CLAUDE.md §0.1: replies to the owner are always bilingual (English + Chinese).

### Tests / checks
Docs-only change; checks re-run — pass.

### Next
Phase 2 (Dataset foundation) on branch `phase2` created from `phase1`.

---

## 2026-09-27 — Phase 1: Framework skeleton (TASK-CORE-001 … 006)

### Branch
`phase1` — based on `phase0` @ `0f04972`

### Objective
Make the project start and its tests run (Gate 1): workspace layout, architecture enforcement,
configuration, logging, plugin registry, API skeleton and CI. No domain logic.

### Changes
- **CORE-001** uv workspace: `scenarios/warehouse` is the separate package `industrial-ai-warehouse`
  (ADR-004), installed via the root dev group only; framework layer packages created
  (`core`, `foundation`, `scenario`, `synthetic`, `simulation`, `application`, `api`).
- **CORE-002** `tests/unit/test_architecture.py` statically enforces R1 (no scenario-pack imports in
  the framework) and R2 (per-layer dependency table, now documented in architecture.md §2, EN + ZH).
  Verified to fail on an injected violation.
- **CORE-003** `core.config.Settings` (pydantic-settings, `IAI_*`, `.env`), `load_settings()`,
  `core.logging.configure_logging()` / `get_logger()`, `core.errors`.
- **CORE-004** `core.registry.Registry[T]` keyed by `(id, semver)`, `core.versioning`; plugin-spec
  (EN + ZH) documents the implemented API.
- **CORE-005** FastAPI `create_app()`, `GET /health`, OpenAPI at `/api/openapi.json`,
  `uv run python -m industrial_ai.api`.
- **CORE-006** GitHub Actions CI: `uv sync --locked`, ruff format/lint, mypy, pytest.

### Dependencies added
Runtime: pydantic, pydantic-settings, fastapi, uvicorn. Dev: httpx2 (Starlette TestClient; `httpx`
is deprecated there).

### Decisions / assumptions
- Phase 1 tasks were small, so they were implemented directly on `phase1` as atomic commits rather
  than separate `feature/*` branches.
- The generic `scenario` layer sits between foundation and synthetic/simulation in the dependency
  table (synthetic generators and simulation plugins both receive a `ScenarioSpec`).
- `api` may import only `core` and `application` (strict reading of ADR-001).
- `Registry` takes a key function so each plugin protocol keeps its own id/version attribute names.

### Files / Modules
`pyproject.toml`, `uv.lock`, `.env.example`, `README.md`, `.github/workflows/ci.yml`,
`src/industrial_ai/{core,foundation,scenario,synthetic,simulation,application,api}/`,
`scenarios/warehouse/`, `tests/unit/`, `tests/integration/`, `docs/architecture.md`,
`docs/plugin-spec.md`, `docs/task-backlog.md` (+ ZH mirrors).

### Tests / checks
ruff format + lint, mypy strict (both packages), pytest: 56 passed (unit + integration).
Manual: API started with uvicorn, `GET /health` → `{"status":"ok","version":"0.1.0.dev0"}`.
CI: GitHub Actions run #1 on `phase1` @ 3a1b8e4 — success (https://github.com/WZcit223/Project1/actions/runs/36307244146).

### Commits
7fcb8a9 build(workspace), e7372eb test(architecture), cddf953 feat(core) config/logging,
afc25ed feat(core) registry, 462ee68 feat(api), 3a1b8e4 ci, + docs(log) for this entry.

### Known issues
- `foundation`, `scenario`, `synthetic`, `simulation`, `application` are still empty packages (by design).
- No database yet; `IAI_DATABASE_URL` is used from Phase 2.

### Next
Owner review of Gate 1 → Phase 2 (Dataset foundation, TASK-DATA-001 …) on branch `phase2` from `phase1`.

---

## 2026-09-27 — Gate 0 approved

### Branch
`phase0`

### Objective
Record the project owner's Gate 0 approval of the architecture baseline.

### Changes
- All specs (EN + ZH) marked "Approved at Gate 0 (2026-09-27), v0.1 baseline".
- ADR-001 … ADR-004 status: Accepted.
- Task backlog: M0 ✅, TASK-ARCH-001 approved. README status updated.
- Approval is recorded here, not via a PR: per CLAUDE.md §7 nothing is merged to `main` during work in progress.

### Tests / checks
Docs-only change; ruff, mypy, pytest and link check re-run — pass.

### Next
Phase 1 (Skeleton): branch `phase1` created from `phase0`, starting with TASK-CORE-001.

---

## 2026-09-27 — Branch policy update

### Branch
`phase0` (renamed from `claude/focused-lamport-421rvy`, then from `phase1` so that branch numbers match backlog phase numbers)

### Objective
Adopt the owner's branching policy: one new branch per major round (phase / feature / function),
created from the latest working branch; no merges to `main` while work is in progress.

### Changes
- CLAUDE.md §7 rewritten (stacked `phase<N>` / `feature/<name>` branches, N = backlog phase number,
  so Phase 0 → `phase0`, Phase 1 → `phase1`; `main` updated only at
  owner-chosen milestones, lineage recorded in this log).
- Task backlog (EN + ZH) references updated; TASK-ARCH-001 branch is `phase0`.

### Tests / checks
Docs-only change; ruff, mypy, pytest and link check re-run — pass.

### Next
Gate 0 review, then Phase 1 (TASK-CORE-001 …) on branch `phase1` created from `phase0`.

---

## 2026-09-27 — TASK-ARCH-001 Architecture baseline

### Branch
`phase0` (based on `main` @ `c3a62bc`; originally pushed as the session branch `claude/focused-lamport-421rvy`, renamed to `phase0`)

### Objective
Establish the architecture baseline (Phase 0) for review at Gate 0: project environment, working
rules, specifications, ADRs and task backlog. No application logic.

### Repository state found
- `main` existed with a single "Initial commit" (README only). No Python project, no other branches.

### Changes
- Initialised uv project (`pyproject.toml`, `uv.lock`, Python ≥ 3.11), dev tools pytest / ruff / mypy.
- Added `.gitignore` (data directories, env, caches), `.env.example`, README with doc index.
- Added `CLAUDE.md` master instruction (used instead of `AI-AGENT.md`, as confirmed).
- Added specs: requirements, scope, architecture, data model, Synthetic Data API, Simulation API,
  Application API, plugin spec, scenario spec, UI spec, validation, task backlog, future roadmap.
- Added ADR-001 … ADR-004.
- Added Chinese mirror of the specs in `docs/zh/`.

### Decisions / assumptions (confirmed with user)
- Single-echelon stocking (store = stocking point), lost sales.
- Service level = fill rate; stockout rate = share of item-days with lost sales; inventory cost =
  holding + ordering; lost-sales value reported separately.
- Demo subset default CA_1 × FOODS_3, top 50 items; real M5 stays local (Kaggle rules); tests use
  a synthetic M5-shaped fixture; subset uploaded by the user when needed.
- Docs bilingual: English authoritative (v1), Chinese mirror (v2) in `docs/zh/`.
- Refinement vs instruction §29 (ADR-004): inventory simulation & strategies live in the warehouse
  scenario pack, which is a separate uv workspace package.
- pandas chosen over Polars for v0.1 (one frame library).

### Files / Modules
`pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`, `.env.example`, `README.md`,
`CLAUDE.md`, `src/industrial_ai/__init__.py`, `tests/unit/test_package.py`, `docs/**`.

### Tests / checks
`uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`, `uv run pytest` — all pass
(1 smoke test). Markdown relative links checked by script.

### Commits
chore(project) ec8f410, docs(agent) 1b5b03f, docs(spec) 60e0ee9 / 99d7f25 / 4b0ccfb,
docs(adr) 3fc3e04, docs(plan) 0060334, docs(zh) ×2, docs(log) (this entry).

### Known issues
- Scenario numeric defaults and Level-3 thresholds are proposals; tune after first Golden Path run.
- Chart library for the UI not yet chosen (Phase 13).
- Network policy of the cloud environment blocks kaggle.com; M5 subset must be supplied by the user.

### Next
Gate 0 review → branch `phase1` created from `phase0` for TASK-CORE-001 (workspace & package skeleton). No merge to `main` during work in progress.
