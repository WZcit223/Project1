# Development Log

Human-readable record of every meaningful development round (newest first).
Fields: Date · Branch · Objective · Changes · Files / Modules · Tests · Commit · Known Issues · Next.

---

## 2026-09-27 — Phase 9: Replenishment strategies (TASK-STR-001 … 003)

### Branch
`phase9` — based on `phase8` @ `91861dc`

### Objective
Three replenishment strategies behind the Phase 8 protocol, compared on identical demand via
`engine.compare` (Gate 8).

### Changes
- `reorder_point` 1.0.0 (s, Q) from mean historical demand, no safety stock; `safety_stock` 1.0.0 (s, S)
  from the forecast and forecast-error std, fixed at the horizon start; `dynamic` 1.0.0 periodic
  order-up-to every R days from the latest forecast and recent errors. `builtin_strategies()` registry.
- `derived.demand_timeline` + `build_demand_timeline()`: observed sales followed by the synthetic horizon
  demand — the input of the rolling forecast during a simulation (no look-ahead).
- Gate 8 integration test: fixture → operations → demand → timeline → seasonal-naive forecast with
  56-day warm-up → inventory simulation × 3 strategies.
- Specs: plugin-spec §4, scenario-spec §6, data-model §3, simulation-api status (EN + ZH).

### Decisions / assumptions (for review)
- R = the item's `order_cycle_days` (14) for all three (override `cycle_days`). The dynamic strategy
  orders every R days, not on every daily review, so its order frequency is comparable with A and B.
- σ_e comes from forecast errors before the horizon: the forecast run starts a **warm-up** (56 days)
  before the horizon and needs `forecast_horizon_days` ≥ reforecast interval + L̄ + R (56 used).
  Missing warm-up or coverage raises an error rather than falling back silently.
- B's levels are set at the first review (horizon start) because `ItemContext` has no date; the
  protocol stays unchanged.
- Forecast demand is read from the day after the review (the order cannot serve today's demand);
  μ_f is the mean over ⌈L̄ + R⌉ days, scaled to L̄ + R.
- σ_e scales with √days (independent daily errors); lead-time variability is not in the safety stock
  (textbook formula as specified).
- A with no demand history never orders.

### Real-subset check (descriptive only; CA_1 / FOODS_3 / top 50, 91 days, seed 20260927)
Service level (inventory cost USD) — reorder_point / safety_stock / dynamic:
- baseline: 0.847 (18,361) / 0.862 (19,400) / 0.938 (18,625)
- high_demand ×1.3: 0.750 (20,610) / 0.777 (21,492) / 0.911 (18,742)
- supply_disruption (+7 d, 50 %, days 28–69): 0.669 (19,014) / 0.711 (20,526) / 0.776 (18,369)
The dynamic strategy holds about twice the stock (holding 829 vs 444 USD at baseline); ordering cost
(~18 k USD) still dominates. ≈ 5 s per scenario incl. forecast.

### Tests / checks
ruff format, ruff, mypy strict, pytest: 280 passed (hand-computed rules for each strategy, warm-up and
coverage errors, timeline, Gate 8 comparison, reproducibility, high demand hurts the static strategy more).

### Commits
e863502 feat(warehouse): demand timeline · 3ca286d feat(warehouse): three strategies ·
0021a7e test(warehouse): Gate 8 comparison · 039f239 docs(spec) · docs(zh) / docs(plan) / docs(log) (this round).

### Known issues
- Ordering cost dominates inventory cost (synthetic order cost 20–60 USD vs low FOODS_3 unit costs), so
  "inventory cost" mostly measures order count; consider tuning `OperationsConfig.order_cost_range`
  (owner decision, affects the demo narrative).
- Safety stock B only modestly beats A: its σ_e is estimated at the start and fixed, and the textbook
  formula ignores lead-time variability.

### Next
Gate 8 / M9 review → Phase 10 (scenario engine) on branch `phase10` from `phase9`.

---

## 2026-09-27 — Gate 7 / M8 approved

### Branch
`phase8`

### Changes
- Owner approved Gate 7 (inventory simulation works) and the seven Phase 8 decisions (strategy protocol
  delivered early, CRN pre-sampling, unshipped share lost, duration 0 = whole horizon, capacity reported
  only, lost-sales value at mean price, initial on_order after mean lead time). M8 ✅ in the backlog (EN + ZH).

### Next
Phase 9 (replenishment strategies) on branch `phase9` created from `phase8`.

---

## 2026-09-27 — Phase 8: Inventory simulation + metrics (TASK-INV-001, TASK-INV-002)

### Branch
`phase8` — based on `phase7` @ `57c0bb4`

### Objective
Warehouse inventory simulation plugin (daily, single-echelon, lost sales) with ledger and purchase-order
outputs and the KPI set of data-model §6; Gate 7.

### Changes
- Strategy protocol in `industrial_ai_warehouse.strategies` (`ReplenishmentStrategy.create_policy` →
  `ItemPolicy.order_quantity`, `ItemContext`, `DailyObservation`, `ForecastView` without look-ahead,
  strategy registry). Delivered here because the simulation needs it; the three strategies follow in Phase 9.
- `inventory_simulation` 1.0.0: receive → serve → review → order; case pack / MOQ rounding; sampled lead
  times with late deliveries; supply scenario effects (`lead_time_delta`, `supply_capacity_factor`,
  disruption window, `planner_aware`); outputs `sim.inventory_ledger` and `sim.purchase_order`.
- `inventory_metrics`: all data-model §6 metrics plus per-product service level.
- Specs updated: scenario-spec §5, plugin-spec §4, data-model §4/§6 (EN + ZH).

### Decisions / assumptions (for review)
- Strategy protocol defined in Phase 8 (backlog had it in TASK-STR-001) and changed from the Gate 0 sketch
  (`initialise`/`decide`/`OrderDecision`) to `create_policy`/`order_quantity`; rounding stays in the simulation.
- Lead-time noise, lateness and delays are pre-sampled per item and day (common random numbers), so strategies
  compared on the same seed see the same supply conditions.
- The unshipped share under reduced supply capacity is lost (not back-ordered).
- `disruption_duration_days = 0` means the whole horizon.
- Warehouse capacity is reported as a warning when exceeded, not enforced (v0.1).
- Lost-sales value uses the mean reference price (`derived.product_price`).
- Initial `on_order` (0 by default) would arrive after the mean lead time.

### Real-subset check (descriptive only, not committed as a test)
CA_1 / FOODS_3 / top 50, 91-day synthetic horizon, seed 20260927, temporary test order-up-to strategy
(daily review): level 100 → service 0.668, level 300 → 0.929; supply disruption (+7 days lead time, 50 %
capacity, days 14–41) → 0.574 / 0.879. ≈ 0.7 s per run. Ordering cost (≈ 143 k USD) dwarfs holding cost
(≈ 156 USD), because the test strategy orders almost daily and FOODS_3 unit costs are low.

### Tests / checks
ruff format, ruff, mypy strict, pytest: 265 passed (accounting identities, hand-computed 10-day example,
metric recomputation from the ledger, CRN, scenario effects, Gate 7 pipeline on the fixture).

### Commits
412e62c feat(warehouse): strategy protocol · 0b51933 feat(warehouse): inventory simulation + metrics ·
docs(spec) / docs(zh) / docs(plan) / docs(log) (this round).

### Known issues
- Cost balance of the synthetic operations (order cost 20–60 USD vs. low FOODS_3 unit costs) makes ordering
  cost dominate; review when the Phase 9 strategies with order cycles run on the real subset.
- Capacity not enforced; single echelon; no backorders (by scope).

### Next
Gate 7 / M8 review → Phase 9 on branch `phase9` (from `phase8`): reorder point, safety stock, dynamic
strategies, compared on identical demand via `engine.compare` (Gate 8).

---

## 2026-09-27 — M7 approved

### Branch
`phase7`

### Changes
- Owner approved milestone M7 and the five Phase 7 decisions (native LightGBM API, direct multi-step,
  no price/event features in v1, forecasts beyond the last observation, 4-week seasonal naive).
  M7 ✅ in the backlog (EN + ZH).

### Next
Phase 8 (inventory simulation + metrics) on branch `phase8` created from `phase7`.

---

## 2026-09-27 — Phase 7: Forecast plugins (TASK-FC-001, TASK-FC-002) · M5 subset committed

### Branch
`phase7` — based on `phase6` @ `d82f973`

### Objective
Domain-neutral forecast plugins for the Data → Forecast → Simulation pipeline: one baseline pair and
one practical ML model, rolling-origin, provably without look-ahead.

### Changes
- **M5 subset (owner decision, option B):** real subset committed in `data/reference/m5_subset/`
  (65222ec) with a README on origin and Kaggle terms; CLAUDE.md §13 records the single exception;
  `m5_local` tests read it (and therefore also run in CI).
- `simulation.forecasting.rolling`: rolling origins (every 7 days, 28-day horizon), history strictly
  before each origin, `sim.forecast` output with actuals, MAE / RMSE / WAPE / bias.
- `seasonal_naive` 1.0.0 (mean of last 4 same-weekday values), `moving_average` 1.0.0 (28-day mean),
  `lightgbm` 1.0.0 (global Poisson model trained once before the horizon; native API, deterministic).
- `PluginOutput.details` recorded in provenance (e.g. LightGBM training rows, features, importance).
- simulation-api.md §4 documents the implemented plugins (EN + ZH).

### Decisions / assumptions (for review)
- LightGBM via the native `lgb.train` API: the scikit-learn wrapper would add scikit-learn.
  `lightgbm` brings `scipy` as a transitive dependency.
- Direct multi-step LightGBM (horizon day as a feature) instead of recursive prediction: no error
  feedback loop, simpler no-look-ahead guarantee.
- v1 features have no price or event inputs (kept domain-neutral); candidates for a later version.
- Forecasts beyond the last observed date are produced (needed for lead-time planning near the horizon
  end) and have `actual = null`.
- Seasonal naive default averages 4 weeks (N = 1 is the textbook version; 4 is more robust).

### Real-subset check (m5_local test)
50 series, 26 weekly origins, 2015-11-23 … 2016-05-22: WAPE seasonal naive 0.443, moving average 0.459,
LightGBM 0.413 (bias +0.8 %). LightGBM run ≈ 2 s (141,400 training rows). Descriptive only.

### Tests / checks
ruff, mypy strict, pytest: 248 (incl. no-look-ahead tests for all three plugins).

### Commits
65222ec M5 subset, 45c4182 forecast plugins, aaffb3c real-subset forecast test, + docs commits.

### Known issues
- The input to forecasting during a scenario run (history + observed synthetic horizon demand) is
  assembled by the application pipeline (Phase 11); plugins take any observed series.

### Next
Owner review of M7 → Phase 8 (inventory simulation + metrics) on `phase8` from `phase7`.

---

## 2026-09-27 — Gate 6 approved

### Branch
`phase6`

### Changes
- Owner approved Gate 6 and the four Phase 6 decisions (engine-only datasets/provenance, no failed
  result objects, upstream by name, constraints passed to plugins). M6 ✅ in the backlog (EN + ZH).
- Owner chose option B for the real M5 subset (commit it; the repository will be made private later)
  and explicitly accepted that it is publicly visible until then. Implemented on `phase7`.

### Next
Phase 7 (forecast plugins) on branch `phase7` created from `phase6`.

---

## 2026-09-27 — Phase 6: Simulation Engine (TASK-SIM-001)

### Branch
`phase6` — based on `phase5` @ `c16d16c`

### Objective
Gate 6: the simulation engine executes registered plugins, composes them through upstream results
and compares variants — with provenance, validation and no fake results.

### Changes
- `industrial_ai.simulation`: `SimulationPlugin` protocol, `PluginKind` (optimization / causal
  reserved), `RunContext` (horizon, seed, named upstream), `PluginOutput` / `OutputTable`, `Metric`,
  `SimulationResult`, `RunMetadata`, registry (`describe`, `plugins_of_kind`), `SimulationEngine.run()`
  and `.compare()` → `ComparisonResult.metrics_table()`.
- simulation-api.md §1–3 describe the implemented interfaces (EN + ZH).

### Decisions / assumptions (for review)
- Plugins return `PluginOutput`; only the engine builds datasets, provenance and metadata (same pattern
  as synthetic generators).
- No `failed` status objects: every failure raises; `status` is always `succeeded`. (The Gate 0 sketch
  mentioned "succeeded or failed".)
- Upstream results are passed by name in the `RunContext`; their tables become provenance inputs of
  downstream outputs.
- Output tables are validated against their schemas; the run's `constraints` are passed to the plugin
  (e.g. for capacity rules) rather than applied to outputs.
- `compare()` uses the same seed for all variants (common random numbers).

### Tests / checks
ruff, mypy strict, pytest: 231 passed locally (incl. `m5_local`); 8 new engine tests with a dummy
forecast and a dummy stock simulation.

### Commits
73c4311 simulation engine, + docs commit.

### Next
Owner review of Gate 6 → Phase 7 (forecast plugins: seasonal naive, moving average, LightGBM) on
`phase7` from `phase6`.

---

## 2026-09-27 — Gate 5 approved

### Branch
`phase5`

### Changes
- Owner approved Gate 5 and the five Phase 5 decisions (supplier / lead-time split,
  strategy-independent policy settings, no `as_of_date`, operational defaults as assumptions, common
  random numbers). M5 ✅ in the backlog (EN + ZH).
- Owner asked whether the real M5 subset can be pushed to GitHub. Not done: the repository is public
  and the data is under Kaggle competition rules (no redistribution; CLAUDE.md §13). Options put to
  the owner for decision.

### Next
Phase 6 (Simulation Engine) on branch `phase6` created from `phase5`.

---

## 2026-09-27 — Phase 5: Synthetic warehouse data (TASK-WH-001)

### Branch
`phase5` — based on `phase4` @ `4e74edf`

### Objective
Gate 5: warehouse operational data can be generated — reproducibly, validated, with provenance —
completing the Hybrid Validation Environment (real M5 demand + synthetic operations).

### Changes
- `industrial_ai.synthetic.generators.builtin_registry()` (core helper: the three generators).
- Warehouse schemas (1.0.0): `ops.warehouse`, `ops.supplier`, `ops.supplier_lead_time`,
  `ops.product_supplier`, `ops.initial_inventory`, `ops.replenishment_policy`,
  `ops.synthetic_demand`; derived `product_price`, `store_demand`, `planning_input`.
- `generate_operations(retail, seed, config)`: every `ops.*` table via the engine (rule_based /
  statistical), assumptions in `OperationsConfig`, per-table derived seeds, lineage with config and seed;
  `build_hybrid_bundle()`.
- `generate_synthetic_demand(retail, DemandConfig, seed, scenario)`: calibrated time series with
  `demand_multiplier → level_multiplier`, common random numbers across scenarios.
- data-model.md §3 rewritten for the implemented tables and rules (EN + ZH).

### Decisions / assumptions (for review)
- Supplier lead-time parameters split into `ops.supplier_lead_time` (statistical) from `ops.supplier`
  (rule_based), so each table has one generator and a complete provenance chain.
- `ops.replenishment_policy` holds strategy-independent settings (review period 1 day, order cycle
  14 days, target service level 0.95); strategies derive reorder points etc. at run time (Phase 9).
  Replaces the earlier `(…, strategy_id)` + JSON parameters sketch.
- `as_of_date` dropped from `ops.initial_inventory`: the initial state is by definition at the
  simulation start.
- Derived tables (`derived.*`) are explicit datasets with provenance rather than hidden computations.
- Operational defaults (5 suppliers, lead time mean ≈ 6.3 d, cost ratio 0.7, holding 25 %/yr,
  capacity 60 days of demand, initial stock μ·(L̄ + 7)) are illustrative assumptions, not facts.
- Common random numbers for scenario demand (same seed stream for all scenarios).

### Real-subset check (local, not committed)
Operations for `m5_subset_ca_1_foods_3_top50` generated in 0.3 s; hybrid bundle 194 checks,
0 failed, 0 skipped. 1 warehouse (CA_1, capacity 43,879 units); supplier mean lead times 4.5–9.7 days;
unit costs 0.14–3.49 USD; products per supplier 10/8/13/5/14; initial on-hand 10,066 units
(13.8 days of demand).

### Tests / checks
ruff, mypy strict, pytest: 223 passed locally (incl. `m5_local`); CI skips `m5_local`.

### Commits
76a3ede builtin_registry, fdabfff operations + demand, + docs commit.

### Known issues
- With the small fixture and negative-binomial noise, the High-Demand demand ratio varies ±6 % around
  1.3 across seeds even with common random numbers; the scenario effect itself is exact (tested with
  noise off). Phase 14 Level-3 checks should use the noise-free rate or a larger horizon/sample.

### Next
Owner review of Gate 5 → Phase 6 (Simulation Engine: protocol, result model, registry, engine) on
`phase6` from `phase5`.

---

## 2026-09-27 — Gate 4 approved

### Branch
`phase4`

### Changes
- Owner approved Gate 4 and the four Phase 4 decisions (engine-only provenance, generic scenario
  effect names with pack mapping, no trend / calibrated event uplift in v1, Iman–Conover correlation).
  M4 ✅ in the backlog (EN + ZH).

### Next
Phase 5 (synthetic warehouse operational data) on branch `phase5` created from `phase4`.

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
