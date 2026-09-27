# Data Model — v0.1

Status: **Approved at Gate 0 (2026-09-27), v0.1 baseline** · 中文: [zh/data-model.md](zh/data-model.md) · Related: [ADR-003](adr/ADR-003-m5-canonical-adapter.md)

This document defines (1) the domain-neutral dataset abstraction of the framework,
(2) the canonical retail-demand model used by the Warehouse pack, (3) the synthetic operational
entities, (4) simulation output tables, (5) M5 mapping and (6) **metric definitions**.

## 1. Framework dataset abstraction (domain-neutral, `industrial_ai.foundation`)

### 1.1 `FieldSpec`

| Attribute | Type | Notes |
|---|---|---|
| `name` | str | snake_case column name |
| `dtype` | enum | `int`, `float`, `str`, `bool`, `date`, `datetime`, `category` |
| `nullable` | bool | default `false` |
| `unit` | str \| null | e.g. `units`, `USD`, `days` |
| `min` / `max` | number \| null | inclusive range constraint |
| `allowed_values` | list \| null | for categorical fields |
| `description` | str | human-readable meaning |

### 1.2 `DatasetSchema`

| Attribute | Type | Notes |
|---|---|---|
| `schema_id` | str | e.g. `retail_demand.sales` |
| `schema_version` | semver str | bump on any breaking change |
| `fields` | list[FieldSpec] | ordered |
| `primary_key` | list[str] | uniqueness constraint |
| `foreign_keys` | list[{fields, ref_schema_id, ref_fields}] | relationship constraints |
| `time_index` | str \| null | field holding the time axis |
| `entity_keys` | list[str] | fields identifying the entity series (e.g. `product_id`, `store_id`) |

### 1.3 `Dataset`

| Attribute | Type | Notes |
|---|---|---|
| `dataset_id` | str | stable id, e.g. `m5_subset_ca1_foods3` |
| `version` | str | dataset version |
| `schema` | DatasetSchema | |
| `data` | pandas.DataFrame | in-memory; persisted as Parquet artifact |
| `metadata` | DatasetMetadata | see below |
| `provenance` | ProvenanceRecord | see [synthetic-data-api.md §5](synthetic-data-api.md#5-provenance) |

Datasets are created with `build_dataset(dataset_id, version, schema, data, source, lineage)`, which
reorders columns to schema order and **computes** row count, content hash, time range, entity counts
and the provenance output from the data. A `Dataset` re-checks these invariants on construction, so its
metadata and provenance can never disagree with its data. Value-level checks are separate
(`validate_dataset`, see §1.5).

A logical dataset composed of several tables (e.g. sales + prices + calendar) is a **`DatasetBundle`**:
`bundle_id`, `version`, `tables: dict[str, Dataset]`, `source`, `lineage`; its `content_hash` is
derived from the member tables' names and hashes.

### 1.4 `DatasetMetadata`

| Attribute | Notes |
|---|---|
| `name`, `description` | Fields supplied by the producer (`SourceInfo`): name … tags |
| `source_type` | `reference` (real external), `synthetic`, `derived`, `fixture` |
| `source` | e.g. `M5 Forecasting Accuracy` |
| `source_url` | |
| `dataset_version` / `download_date` | for external sources |
| `license_notes` | e.g. "Kaggle competition rules; do not redistribute" |
| `time_range` | `{start, end}` |
| `row_count` | computed |
| `entity_counts` | computed: distinct values per entity key, e.g. `{"product_id": 50}` |
| `created_at` | UTC timestamp |
| `content_hash` | computed: `sha256:` over values per column (sorted by name, logical dtype family, row order kept, index ignored); unchanged by a Parquet round trip |
| `tags` | free-form labels (e.g. `demo`, `prototype`) |

### 1.5 Validation (`industrial_ai.foundation.validation`)

`validate_dataset(dataset, constraints=(), references=None)` and `validate_bundle(bundle, constraints)`
return a `ValidationReport` (`subject`, `results`, computed `passed`). Each `CheckResult` has `check`,
`target`, `status` (`passed` / `failed` / `skipped`), `violations` (offending rows) and `message`.

| Check | From | Rule |
|---|---|---|
| `dtype` | schema | Column matches the logical type (`date` values must have no time component; `str` values must be strings) |
| `not_null` | schema (`nullable=false`) / constraint | No missing values |
| `range` | schema `min`/`max` / constraint | Numeric values within bounds; **skipped** if the column has the wrong dtype |
| `allowed_values` | schema | Values in the allowed set |
| `primary_key` | schema | No duplicate and no null keys |
| `foreign_key` | schema / constraint | Every key exists in the referenced table; **skipped** when that table is not supplied (a bundle supplies its own tables) |
| `unique`, `integer`, `relation` | constraint | Uniqueness of fields; integral values; row-wise comparison `left op right` |

Validation never modifies data and never raises for bad data. `skipped` checks do not fail a report
but are always listed, so nothing is silently treated as passed.

### 1.6 Catalog (`industrial_ai.foundation.catalog.DatasetCatalog`)

SQLite (via SQLModel; `IAI_DATABASE_URL`) holds one row per dataset and per bundle with the schema,
metadata and provenance as JSON; the data is a Parquet file under
`<IAI_DATA_DIR>/processed/artifacts/datasets/<dataset_id>/<version>/data.parquet`.

| Operation | Behaviour |
|---|---|
| `register(dataset)` | Writes Parquet, **re-reads it and checks the content hash** before committing; duplicate `(dataset_id, version)` → `DatasetAlreadyRegisteredError` |
| `get(dataset_id, version=None)` | Rebuilds the `Dataset`; the hash is re-verified, so a modified artifact raises `DatasetError`; `version=None` = most recently registered |
| `list(source_type=None)` | `DatasetSummary` rows in registration order |
| `preview(dataset_id, version=None, limit=50)` | Summary, per-column stats (dtype, nulls, min/max, mean) and the first rows as JSON-safe dicts |
| `register_bundle(bundle)` / `get_bundle(...)` | Stores member-table references; identical already-registered tables are reused, conflicting ones rejected |

Dataset versions are free-form strings (e.g. `"1"`, `"2026-09-27"`); plugin and schema versions are semver.

### 1.7 Ingestion (`industrial_ai.foundation.ingestion`)

- `load_table(path, schema, dataset_id=…, version=…, source=…)` reads a `.csv` or `.parquet` file whose
  columns are exactly the schema's fields. CSV text is converted per logical type (`int` → `int64`, or
  `Int64` if it has missing values; `bool` accepts true/false/1/0/yes/no; dates are ISO 8601). A value
  that cannot be converted raises `IngestionError` naming the column and examples — it is never
  silently turned into a missing value. Provenance records the loader (`tabular_loader` 1.0.0), the
  file name, format and the file's SHA-256 (no machine-specific paths).
- `DatasetAdapter` protocol (`adapter_id`, `adapter_version`, `description`, `load(source) → DatasetBundle`)
  and `new_adapter_registry()`. Concrete adapters (e.g. M5) live in scenario packs (ADR-003).

## 2. Canonical retail-demand model (Warehouse pack, `schema_version 1.0`)

The framework never sees M5 column names; the M5 adapter produces these tables.

| Table (schema_id) | Primary key | Fields |
|---|---|---|
| `retail.region` | region_id | region_id (e.g. `CA`), name |
| `retail.store` | store_id | store_id, region_id → region |
| `retail.category` | category_id | category_id (e.g. `FOODS`) |
| `retail.department` | department_id | department_id (e.g. `FOODS_3`), category_id → category |
| `retail.product` | product_id | product_id, department_id → department, category_id → category |
| `retail.calendar` | date | date, week_id, weekday (1=Mon…7=Sun), month, year |
| `retail.calendar_snap` | (date, region_id) | date → calendar, region_id → region, snap_active (bool). Long format, so the calendar does not hard-code regions |
| `retail.calendar_event` | (date, event_name) | date → calendar, event_name, event_type (`Sporting`, `Cultural`, `National`, `Religious`) |
| `retail.sales` | (date, product_id, store_id) | date, product_id, store_id, quantity (int ≥ 0, `units`) |
| `retail.price` | (week_id, product_id, store_id) | week_id, product_id, store_id, unit_price (float > 0, `USD`) |

Notes:
- `retail.sales.quantity` is **observed sales**, used as the demand reference. Observed sales under-state
  true demand when stores were out of stock; this limitation is documented, not corrected, in v0.1.
- Missing price weeks (item not yet on sale) are absent rows, not zeros.

## 3. Synthetic operational entities (Warehouse pack)

Generated by the Synthetic Data Engine; all carry provenance and are labelled `source_type=synthetic`.

| Table | Primary key | Fields | Generator |
|---|---|---|---|
| `ops.warehouse` | warehouse_id | warehouse_id, store_id → store, capacity_units (int > 0), holding_cost_rate_annual (0–1) | rule_based |
| `ops.supplier` | supplier_id | supplier_id, lead_time_mean_days (≥ 1), lead_time_std_days (≥ 0), on_time_probability (0–1), order_cost (USD ≥ 0), min_order_qty (int ≥ 0) | rule_based + statistical |
| `ops.product_supplier` | product_id | product_id → product, supplier_id → supplier, unit_cost (USD > 0; = reference price × cost ratio), case_pack (int ≥ 1) | rule_based + statistical |
| `ops.initial_inventory` | (product_id, warehouse_id) | on_hand_units (int ≥ 0), on_order_units (int ≥ 0), as_of_date | rule_based |
| `ops.replenishment_policy` | (product_id, warehouse_id, strategy_id) | strategy_id, parameters (JSON), review_period_days (int ≥ 1), target_service_level (0–1) | rule_based (derived from demand stats) |
| `ops.synthetic_demand` | (date, product_id, store_id) | same fields as `retail.sales`, plus `scenario_id` | time_series |

**Lead time** is modelled as a per-supplier distribution (`ops.supplier`) and sampled per purchase
order inside the simulation; realised lead times are recorded on each purchase order.

## 4. Simulation output tables

| Table | Primary key | Fields |
|---|---|---|
| `sim.inventory_ledger` | (run_id, strategy_id, date, product_id) | opening_on_hand, arrivals, demand, fulfilled, lost_sales, closing_on_hand, on_order, inventory_position, order_qty |
| `sim.purchase_order` | (run_id, strategy_id, po_id) | product_id, supplier_id, order_date, quantity, sampled_lead_time_days, expected_arrival_date, received_date, received_qty, status (`open`, `received`, `partially_received`) |
| `sim.forecast` | (run_id, model_id, origin_date, date, product_id) | forecast_qty, actual_qty (filled after the fact) |
| `sim.metrics` | (run_id, strategy_id, metric_id, scope) | value, unit, scope (`total` or `product:<id>`) |

## 5. M5 → canonical mapping

Reference: Kaggle M5 Forecasting Accuracy. v0.1 uses `calendar.csv`, `sell_prices.csv` and
`sales_train_evaluation.csv` (a superset of `sales_train_validation.csv`: days d_1…d_1941,
2011-01-29 … 2016-05-22).

| M5 | Canonical |
|---|---|
| `calendar.date` | `retail.calendar.date` |
| `calendar.d` (`d_1` …) | join key only; wide → long unpivot of sales |
| `calendar.wm_yr_wk` | `retail.calendar.week_id`, `retail.price.week_id` |
| `calendar.wday` (1 = Saturday) | `weekday` re-encoded ISO (1 = Monday) |
| `calendar.event_name_1/_2`, `event_type_1/_2` | rows in `retail.calendar_event` |
| `calendar.snap_CA/TX/WI` | one `retail.calendar_snap` row per date and region |
| `sales.item_id` | `product_id` |
| `sales.dept_id`, `cat_id`, `store_id`, `state_id` | department_id, category_id, store_id, region_id |
| `sales.d_*` values | `retail.sales.quantity` |
| `sell_prices.sell_price` | `retail.price.unit_price` |

Subset extraction (`scripts/make_m5_subset.py`, run locally by the user): filter by store(s),
category/department and top-N items by total sales; output small CSVs in the original M5 layout into
`data/raw/m5_subset/`, with a `SOURCE.json` recording filters, source file hashes and download date.

## 6. Metrics definitions

All metrics are computed per strategy per run over the **simulation horizon**, aggregated over all
simulated item-days unless the scope says otherwise. Notation: for item *i*, day *t*:
demand *Dᵢₜ*, fulfilled *Fᵢₜ = min(Dᵢₜ, available)*, lost *Lᵢₜ = Dᵢₜ − Fᵢₜ*, closing on-hand *Iᵢₜ*,
unit cost *cᵢ*, unit price *pᵢₜ*, annual holding rate *h*, order cost *k*, horizon length *T* days,
number of items *N*.

| Metric id | Name | Definition | Unit |
|---|---|---|---|
| `demand_total` | Demand | Σ Dᵢₜ | units |
| `service_level` | Service level (**fill rate**) | Σ Fᵢₜ / Σ Dᵢₜ (undefined → reported `null` if Σ D = 0) | ratio 0–1 |
| `stockout_rate` | Stockout rate | #{(i,t) : Lᵢₜ > 0} / (N · T) | ratio 0–1 |
| `lost_sales_units` | Lost sales | Σ Lᵢₜ | units |
| `lost_sales_value` | Lost sales value (reported separately, **not** in inventory cost) | Σ Lᵢₜ · pᵢₜ | USD |
| `avg_inventory_units` | Average inventory level | (1 / T) Σₜ Σᵢ Iᵢₜ | units |
| `avg_inventory_value` | Average inventory value | (1 / T) Σₜ Σᵢ Iᵢₜ · cᵢ | USD |
| `holding_cost` | Holding cost | Σ Iᵢₜ · cᵢ · h / 365 | USD |
| `ordering_cost` | Ordering cost | (number of purchase orders) · k | USD |
| `inventory_cost` | Inventory cost | `holding_cost` + `ordering_cost` | USD |
| `order_frequency` | Order frequency | (number of purchase orders) / (N · T / 7) | orders per item per week |
| `inventory_turnover` | Inventory turnover (annualised) | (Σ Fᵢₜ · cᵢ) / `avg_inventory_value` · 365 / T (reported `null` if avg value = 0) | turns / year |

Purchase cost of goods is excluded from inventory cost (it is identical across strategies given the
same fulfilled demand, apart from end-of-horizon stock). Forecast accuracy metrics (MAE, RMSE, WAPE,
optional M5 WRMSSE as reference) are reported separately by the forecast plugin.
